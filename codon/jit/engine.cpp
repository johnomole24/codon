#include "engine.h"

#include "codon/sir/llvm/llvm.h"
#include "codon/sir/llvm/memory_manager.h"
#include "codon/sir/llvm/optimize.h"

#include "llvm/ExecutionEngine/Orc/CompileOnDemandLayer.h"
#include "llvm/ExecutionEngine/Orc/CompileUtils.h"
#include "llvm/ExecutionEngine/Orc/Core.h"
#include "llvm/ExecutionEngine/Orc/ExecutionUtils.h"
#include "llvm/ExecutionEngine/Orc/IRCompileLayer.h"
#include "llvm/ExecutionEngine/Orc/IRTransformLayer.h"
#include "llvm/ExecutionEngine/Orc/JITTargetMachineBuilder.h"
#include "llvm/ExecutionEngine/Orc/RTDyldObjectLinkingLayer.h"
#include "llvm/ExecutionEngine/Orc/TPCIndirectionUtils.h"
#include "llvm/ExecutionEngine/Orc/TargetProcessControl.h"

namespace codon {
namespace jit {

class Engine {
private:
  std::unique_ptr<llvm::orc::TargetProcessControl> tpc;
  std::unique_ptr<llvm::orc::ExecutionSession> sess;
  std::unique_ptr<llvm::orc::TPCIndirectionUtils> tpciu;

  llvm::DataLayout layout;
  llvm::orc::MangleAndInterner mangle;

  llvm::orc::RTDyldObjectLinkingLayer objectLayer;
  llvm::orc::IRCompileLayer compileLayer;
  llvm::orc::IRTransformLayer optimizeLayer;
  llvm::orc::CompileOnDemandLayer codLayer;

  llvm::orc::JITDylib &mainJD;

  static void handleLazyCallThroughError() {
    llvm::errs() << "LazyCallThrough error: Could not find function body";
    exit(1);
  }

  static llvm::Expected<llvm::orc::ThreadSafeModule>
  optimizeModule(llvm::orc::ThreadSafeModule module,
                 const llvm::orc::MaterializationResponsibility &R) {
    module.withModuleDo(
        [](llvm::Module &module) { ir::optimize(&module, /*debug=*/true); });
    return std::move(module);
  }

public:
  Engine(std::unique_ptr<llvm::orc::TargetProcessControl> tpc,
         std::unique_ptr<llvm::orc::ExecutionSession> sess,
         std::unique_ptr<llvm::orc::TPCIndirectionUtils> tpciu,
         llvm::orc::JITTargetMachineBuilder jtmb, llvm::DataLayout layout)
      : tpc(std::move(tpc)), sess(std::move(sess)), tpciu(std::move(tpciu)),
        layout(std::move(layout)), mangle(*this->sess, this->layout),
        objectLayer(*this->sess,
                    []() { return std::make_unique<ir::BoehmGCMemoryManager>(); }),
        compileLayer(
            *this->sess, objectLayer,
            std::make_unique<llvm::orc::ConcurrentIRCompiler>(std::move(jtmb))),
        optimizeLayer(*this->sess, compileLayer, optimizeModule),
        codLayer(*this->sess, optimizeLayer, this->tpciu->getLazyCallThroughManager(),
                 [this] { return this->tpciu->createIndirectStubsManager(); }),
        mainJD(this->sess->createBareJITDylib("<main>")) {
    mainJD.addGenerator(
        llvm::cantFail(llvm::orc::DynamicLibrarySearchGenerator::GetForCurrentProcess(
            layout.getGlobalPrefix())));
  }

  ~Engine() {
    if (auto err = sess->endSession())
      sess->reportError(std::move(err));
    if (auto err = tpciu->cleanup())
      sess->reportError(std::move(err));
  }

  static llvm::Expected<std::unique_ptr<Engine>> create() {
    auto ssp = std::make_shared<llvm::orc::SymbolStringPool>();
    auto tpc = llvm::orc::SelfTargetProcessControl::Create(ssp);
    if (!tpc)
      return tpc.takeError();

    auto sess = std::make_unique<llvm::orc::ExecutionSession>(std::move(ssp));

    auto tpciu = llvm::orc::TPCIndirectionUtils::Create(**tpc);
    if (!tpciu)
      return tpciu.takeError();

    (*tpciu)->createLazyCallThroughManager(
        *sess, llvm::pointerToJITTargetAddress(&handleLazyCallThroughError));

    if (auto err = llvm::orc::setUpInProcessLCTMReentryViaTPCIU(**tpciu))
      return std::move(err);

    llvm::orc::JITTargetMachineBuilder jtmb((*tpc)->getTargetTriple());

    auto layout = jtmb.getDefaultDataLayoutForTarget();
    if (!layout)
      return layout.takeError();

    return std::make_unique<Engine>(std::move(*tpc), std::move(sess), std::move(*tpciu),
                                    std::move(jtmb), std::move(*layout));
  }

  const llvm::DataLayout &getDataLayout() const { return layout; }

  llvm::orc::JITDylib &getMainJITDylib() { return mainJD; }

  llvm::Error addModule(llvm::orc::ThreadSafeModule module,
                        llvm::orc::ResourceTrackerSP rt = nullptr) {
    if (!rt)
      rt = mainJD.getDefaultResourceTracker();

    return optimizeLayer.add(rt, std::move(module));
  }

  llvm::Expected<llvm::JITEvaluatedSymbol> lookup(llvm::StringRef name) {
    return sess->lookup({&mainJD}, mangle(name.str()));
  }
};

typedef int MainFunc(int, char **);
typedef void InputFunc();

JIT::JIT(ir::Module *module)
    : module(module), pm(std::make_unique<ir::transform::PassManager>(/*debug=*/true)),
      plm(std::make_unique<PluginManager>()),
      llvisitor(std::make_unique<ir::LLVMVisitor>(/*debug=*/true, /*jit=*/true)) {
  if (auto e = Engine::create()) {
    engine = std::move(e.get());
  } else {
    engine = {};
    seqassert(false, "JIT engine creation error");
  }
  llvisitor->setPluginManager(plm.get());
}

void JIT::init() {
  module->accept(*llvisitor);
  auto pair = llvisitor->takeModule();
  auto rt = engine->getMainJITDylib().createResourceTracker();
  llvm::cantFail(
      engine->addModule({std::move(std::get<1>(pair)), std::move(std::get<0>(pair))}));
  auto func = llvm::cantFail(engine->lookup("main"));
  auto *main = (MainFunc *)func.getAddress();
  (*main)(0, nullptr);
  llvm::cantFail(rt->remove());
}

void JIT::run(const ir::Func *input, const std::vector<ir::Var *> &newGlobals) {
  const std::string name = ir::LLVMVisitor::getNameForFunction(input);
  llvisitor->registerGlobal(input);
  for (auto *var : newGlobals)
    llvisitor->registerGlobal(var);
  input->accept(*llvisitor);
  auto pair = llvisitor->takeModule();
  auto rt = engine->getMainJITDylib().createResourceTracker();
  llvm::cantFail(
      engine->addModule({std::move(std::get<1>(pair)), std::move(std::get<0>(pair))}));
  auto func = llvm::cantFail(engine->lookup(name));
  auto *repl = (InputFunc *)func.getAddress();
  (*repl)();
  llvm::cantFail(rt->remove());
}

} // namespace jit
} // namespace codon
