# 30 · 所有权与接口形态（R-OWN）

> 审查状态和接口时，从实际读者、写入者与资源生命周期出发。涉及 C++ 或 Python 绑定的规则按所用语言和运行时契约选读。

## R-OWN-01 按谁决定资源寿命选择所有权

- **内容**：找出负责释放资源的对象、借用者和跨调用保留引用的消费者。表示方式要能区分唯一持有、共享持有和借用。若功能可选，核对关闭时对象是否仍存在，以及构造它是否有成本或副作用。
- **为什么**：把借用者当成持有者会延长寿命，异步消费者只拿到借用又可能在释放后访问。用两个字段描述同一个启用状态，会使调用方承担同步责任。
- **坏例**：
```cpp
std::shared_ptr<ExpertBalancer> expert_balancer_;
expert_balancer_ = std::make_shared<ExpertBalancer>(
    moe->expert_num, moe->expert_num + moe->extra_expert_num, layer_num_, moe_size,
    params.hidden_size, ep_rank, ep_size, world_size, py_eplb, dtype, algo, reporter, cfg);
if (expert_balancer_) { expert_balancer_->step(*this, inputs.warmup); }
```
- **好例**：
```cpp
ExpertBalancer expert_balancer_;   // 成员初始化列表里构造：expert_balancer_(moe_configs, params)
void step(bool warmup) {
  if (!enabled()) return;          // 开关在对象内部判定
  ...
}
// 调用点
expert_balancer_.step(inputs.warmup);   // 无条件调用
```
- **判定**：追到最后一次可能的访问和释放，覆盖回调、任务队列和重载。只看某一时刻的引用计数或调用点数量，无法得知谁需要延长寿命。
- **例外**：延迟构造、节省资源或能力确实缺失时，可选对象能准确表达生命周期。共享所有权也可以是独立消费者延长寿命的必要条件。
- **证据**：
  - `codex/2026-10-22T11-02-06` Turn 1：「我看它也没有往其他地方传，不需要用 shared_ptr，一些是否汇报，是否 balance 逻辑全部在 step 里就行，所以也不需要为 nullptr」｜raw: `/home/baowending.bwd/.codex/sessions/2026/10/22/rollout-2026-10-22T11-02-06-01a1618f-0883-7673-a07d-dc95ebf96d5b.jsonl`
  - `dsh/session-761ecd9b` Turn 8：「ExpertLoadMonitor 为啥是个 shared_ptr，有其他地方用它吗」｜raw: `/home/baowending.bwd/.dsh/sessions/--home-baowending.bwd-RTP-LLM-github-opensource--/session-761ecd9b-2f24-435e-8b68-2622832bea89/session.v4.jsonl.zstd`
  - `claude/11d7031c` Turn 8：「User explicitly wants simple value ownership… no nullable balancer/shared ownership.」｜raw: `/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/11d7031c-b168-4ece-8e6a-09c1df4c29c9.jsonl`

## R-OWN-02 在对象首次可用前建立必要依赖

- **内容**：沿构造、初始化和首次调用检查对象何时满足使用前提。构造阶段已具备的固定依赖可以显式传入，随请求变化的数据留到调用时提供。
- **为什么**：一个对象已发布给其他调用方，却还依赖另一处稍后执行的绑定，过早调用或重载时就会读到空值、旧值或已释放的引用。
- **坏例**：
```cpp
// 示意：调用者要记得先补绑定，每次 step 还要交出整个宿主
ExpertBalancer balancer;
balancer.bind(weights, stats);
balancer.step(model, warmup);   // 新入口若直接调 step 就会跳过上一步
```
- **好例**：
```cpp
// 成员初始化列表一次构造；依赖显式传入，不再二次 init
PyWrappedModel::PyWrappedModel(const GptModelInitParams& params)
    : expert_balancer_(params.description.ffn_conf.moe_configs, params, weights_, stats_) {}

ExpertBalancer(const std::optional<MoeConfigs>& moe, const GptModelInitParams& params,
               Weights& weights, OverallExpertStats& stats);   // 构造期绑定引用
void step(bool warmup = false);                                // 只传变化量
```
- **判定**：定位对象第一次可被使用的位置。检查每个入口如何保证初始化成功，失败时已取得的资源由谁释放，以及借用的依赖是否至少活到最后一次使用。
- **例外**：异步连接、框架回调和可重启服务可能需要独立启动阶段。只要各阶段允许的操作和失败后的清理清晰，就可以保留该接口。
- **证据**：
  - `codex/2026-10-22T11-21-51` Turn 1：「对 eplb_balancer 的构造太复杂了，直接改成 `expert_balancer_ = ExpertBalancer(description_.ffn_conf.moe_configs, params)`；里面初始化时候再构造不好吗」｜raw: `/home/baowending.bwd/.codex/sessions/2026/10/22/rollout-2026-10-22T11-21-51-01a161a1-1e0b-7cf0-b8b2-fec51d24b312.jsonl`
  - `codex/2026-10-22T11-30-49` Turn 5：「step 这个东西，传 *this 好像是没有道理的……直接初始化时候把 weights 引用放进去都比传 *this」｜raw: `/home/baowending.bwd/.codex/sessions/2026/10/22/rollout-2026-10-22T11-30-49-01a161a9-52d2-77e3-8565-097763229970.jsonl`
  - `dsh/session-10b33c8a` Turn 5：「至少这一段应该完全能够放到 eplb_balancer 自己的构造函数里去吧，外面把 params 和 config 传一下就行了」｜raw: `/home/baowending.bwd/.dsh/sessions/--home-baowending.bwd-RTP-LLM-github-opensource--/session-10b33c8a-f66f-4220-9508-d91de9783748/session.v4.jsonl.zstd`

## R-OWN-03 出参是否可省略应与接口约定一致

- **内容**：区分调用方必须提供结果容器、调用方可以放弃结果，以及某次执行恰好没有结果。让接口和实现明确这些情况，并约定容器是覆盖、清空还是追加。
- **为什么**：错误地接受空容器会漏掉必需结果，错误地假定容器为空会把上次数据带给本次调用。
- **坏例**：
```cpp
// 假设这个调用方必须处理逐项失败，但签名接受空指针
Status load(const Batch& b, std::vector<CrcCopyFailure>* failures);
load(batch, nullptr);   // 该调用者拿不到后续处理需要的失败列表
```
- **好例**：
```cpp
// 头文件：Clears failures on entry, then appends per-item failures.
Status load(const Batch& b, std::vector<CrcCopyFailure>& failures);
```
- **判定**：核对调用方能否合法省略出参，带旧内容的容器在成功、失败和无结果时会留下什么。C++ 接口可用引用表达必传，可空指针表达可选，也可以直接返回结果。
- **例外**：跨语言 ABI 可能要求必传出参使用指针。项目中的 `CrcBlockCopy::store/load` 则明确允许调用方放弃收集逐项失败，其可选指针符合约定。
- **证据**：
  - `codex/2026-10-19T15-19-20` Turn 3：「load/store 为啥要传 `std::vector<CrcCopyFailure>* failures`，直接用引用吧」｜raw: `/home/baowending.bwd/.codex/sessions/2026/10/19/rollout-2026-10-19T15-19-20-01a15307-75a1-73f0-bf6a-038e5f8af2e6.jsonl`
  - `codex/2026-10-19T10-40-16` Turn 32：「直接用引用不好吗，应该不会有 nullptr 的情况吧；mapped 是啥含义」｜raw: `/home/baowending.bwd/.codex/archived_sessions/rollout-2026-10-19T10-40-16-01a15207-f8b8-7272-aab3-cb92ad9d4a6d.jsonl`
  - `codex/01a1c90c-cc18-7063-8df2-30bdbddc6977`，2026-11-11 11:07:23 UTC，Turn 未核实，行 1960：「一个&一个*你这个代码质量有点离谱吧」；截图指向 `const torch::Tensor& packed_to_dense` 与 `torch::Tensor* dense_to_packed`｜raw: `/home/baowending.bwd/.codex/sessions/2026/11/11/rollout-2026-11-11T13-20-21-01a1c90c-cc18-7063-8df2-30bdbddc6977.jsonl`

## R-OWN-04 只传所需数据，不传整个上下文对象

- **内容**：从被调用方真正读取的字段和它承诺承担的操作确定参数。若只需一个值，直接传值能减少对宿主内部结构的依赖。一个上下文本来就承载取消、身份或一致快照时，也应核对拆开会损失什么。
- **为什么**：传入整份宿主对象，会让实现悄悄依赖更多字段。对必需字段使用可选访问，又可能掩盖调用者拿错对象。
- **坏例**：
```python
# 下游只需要 expert_token_counts，却把整个 inputs 传一层
forward_layers(inputs=inputs, ..., expert_load_inputs=inputs)
def forward_layers(inputs, expert_load_inputs=None):
    counts = getattr(expert_load_inputs, "expert_token_counts", None)  # 猜字段
```
- **好例**：
```python
forward_layers(..., expert_token_counts=inputs.expert_token_counts)
def forward_layers(..., expert_token_counts: Optional[torch.Tensor] = None):
    expert_load = expert_load_for_layer(expert_token_counts, layer_idx)
```
- **判定**：检查被调用方读取的字段是否构成同一份契约。若缺字段会走默认值，指出这是合法输入还是应暴露的构造错误。
- **例外**：稳定的请求上下文、事务句柄或公开协议可以按整体传递。
- **证据**：
  - `claude/413c0761` Turn 1：「pass the expert count tensor directly instead of the whole input object, use direct attribute access」｜raw: `/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/413c0761-03be-42fb-83ed-54ba68a2b04b.jsonl`
  - `codex/2026-10-19T11-49-52` Turn 5：「看上去只是为了做 buffer 的传递？那为啥不放在 pymodelinput 里？」｜raw: `/home/baowending.bwd/.codex/sessions/2026/10/19/rollout-2026-10-19T11-49-52-01a15247-af39-77c2-9a48-5b49080f4d90.jsonl`

## R-OWN-05 派生状态要能追到权威来源和更新时机

- **内容**：一个值能由已有状态直接得到时，检查增加的镜像、标记或缓存是否承担独立职责。需要快照、延长寿命或节省计算时，明确写入者、失效条件和读者能接受的新旧程度。
- **为什么**：两个可独立修改的字段容易在重置、重载或失败路径上失配。调用方持有旧引用时，重新分配底层存储也可能使引用失效。
- **坏例**：
```cpp
class PyWrappedModel {
  ExpertBalancer expert_balancer_;
  torch::Tensor expert_token_counts_;      // 与 balancer 内部同一块 buffer
  bool monitor_metrics_enabled_ = false;   // 镜像状态，两处赋值
};
```
- **好例**：
```cpp
class PyWrappedModel {
  ExpertBalancer expert_balancer_;
 public:
  // 此例的 graph capture 要求地址在 replay 之前保持有效
  const torch::Tensor& stable_expert_token_counts() const {
    return expert_balancer_.stable_expert_token_counts();
  }
};
```
- **判定**：逐条检查修改、替换和销毁来源的路径，说明读者会看到哪个版本。调用方若依赖引用或地址稳定，检查生命周期约定及代码能否兑现。
- **例外**：一致快照和有明确失效策略的缓存有独立语义。即使二者某时刻的值相同，也要根据它们的读写时序判断是否重复。
- **证据**：
  - `codex/2026-10-22T11-30-49` Turn 3：「expert_token_counts_ 不要作为 PyWrappedModel，直接搞一个 inline 函数从 expert_balancer_ 取吧，然后函数名加上 stable_ 表示 tensor 是固定的」｜raw: `/home/baowending.bwd/.codex/sessions/2026/10/22/rollout-2026-10-22T11-30-49-01a161a9-52d2-77e3-8565-097763229970.jsonl`
  - `claude/11d7031c` Turn 5：「Remove the redundant monitor_metrics_enabled_ member and its two assignments; reportStats uses actual load_monitor_ existence.」｜raw: `/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/11d7031c-b168-4ece-8e6a-09c1df4c29c9.jsonl`

## R-OWN-06 把控制参数放在实际作决策的一层

- **内容**：若调用方已经决定是否执行某个动作，检查传入的标志在被调方还有什么用途。如果多个入口都依赖同一策略，把判断收在能保证一致的一层。
- **为什么**：把「调不调」塞进记录接口会诱导 `recordStep(true)` 这类常量实参；反过来，把被调方真正需要的策略上下文抠掉，会让调用方重复实现同一套判断。
- **坏例**：
```cpp
// 纯记录接口：标志只用于「调不调」，却做成参数
void recordStep(bool warmup);
monitor_->recordStep(inputs.warmup);
```
- **好例**：
```cpp
void recordStep();                       // 只负责提交一个样本
if (!inputs.warmup) {                    // 判断留在调用方
  expert_load_monitor_.recordStep();
}
```
- **判定**：追踪每个标志的来源、可达取值及对调用结果的影响。若它仅在一条路径恒定，先检查其他入口。若多个标志可组合出无效操作，可以用独立方法或具名模式表达有效状态。
- **例外**：同一入口承诺按调用者提供的模式选择操作，或各操作必须遵守共同策略时，控制参数有明确用途。参数能否准确表达合法调用比数量更有判断力。
- **证据**：
  - `dsh/session-761ecd9b` Turn 31：「recordstep 为啥要加 warmup（直接外面 !warmup recordstep 不好吗）」｜raw: `/home/baowending.bwd/.dsh/sessions/--home-baowending.bwd-RTP-LLM-github-opensource--/session-761ecd9b-2f24-435e-8b68-2622832bea89/session.v4.jsonl.zstd`
  - `codex/2026-10-22T11-02-06` Turn 1：「一些是否汇报，是否 balance 逻辑全部在 step 里就行」｜raw: `/home/baowending.bwd/.codex/sessions/2026/10/22/rollout-2026-10-22T11-02-06-01a1618f-0883-7673-a07d-dc95ebf96d5b.jsonl`

## R-OWN-07 运行期数据的来源和生命周期应可追踪

- **内容**：检查每次请求使用的数据如何到达消费者。若初始化代码通过私有字段、模块名或遍历顺序注入运行期状态，追踪增加实现或替换实例后，谁会把数据交给新消费者。
- **为什么**：隐式绑定依赖内部结构（`_strategy`、`router`、文件名），换实现就静默失效，还会产生二次绑定与「重新初始化后再绑一次」的补丁。
- **坏例**：
```python
def bind_expert_load_monitor(model, buf):
    for i, layer in enumerate(model.layers):
        layer.fused_moe._strategy.router.expert_counts = buf[i]   # 猜私有字段
        if layer.__class__.__module__.endswith("mega"):
            layer.rank_owner = self.tp_rank                       # 靠文件名定 rank
```
- **好例**：
```python
inputs.expert_load = ExpertLoadBuffers(counts=counts)
for layer_id, layer in enumerate(self.layers):
    layer(x, expert_load=expert_load_for_layer(inputs.expert_load.counts, layer_id))
```
- **判定**：沿构造、重载和一次真实调用追踪写入者与读者。指出哪项受支持的变化会使某个消费者拿不到数据、拿到其他请求的数据或拿到过期引用。
- **例外**：稳定依赖可以在构造时绑定。框架提供的注册或上下文接口如果明确约定作用域和释放时机，也可以承担传递职责。
- **证据**：
  - `codex/2026-10-16T14-13-13` Turn 1：「然后看下 bind_expert_load_monitor 这个东西，感觉不是很合理」｜raw: `/home/baowending.bwd/.codex/sessions/2026/10/16/rollout-2026-10-16T14-13-13-01a14357-d9f8-7643-9995-387cb01f0c18.jsonl`
  - `codex/2026-10-19T11-49-38` Turn 5：「看上去只是为了做 buffer 的传递？那为啥不放在 pymodelinput 里？」；Turn 6：「是的，我觉得这样做更好」｜raw: `/home/baowending.bwd/.codex/sessions/2026/10/19/rollout-2026-10-19T11-49-38-01a15247-7b12-7f22-a074-033777c9fae0.jsonl`

## R-OWN-08 让接口名准确表达调用者能依赖的行为

- **内容**：从调用点核对名称和文档承诺的范围、产生的结果与关键副作用。名称过窄会掩盖实际影响，过宽会让调用方以为尚未支持的输入也得到了处理。
- **为什么**：读者可能从名称推断校验覆盖了全部输入，或某次调用一定会发出事件，进而省略仍然需要的检查。
- **坏例**：
```cpp
// 这处公开入口承接 graph 输入校验，名字只表达其中一个字段
void checkExpertTokenCountsStable(const PyModelInputs& a, const PyModelInputs& b);
```
- **好例**：
```cpp
// graph 输入稳定性检查入口。当前检查范围为 expert_token_counts 的存储和元数据。
void checkGraphInputStable(const PyModelInputs& actual, const PyModelInputs& captured) const;
```
- **判定**：找出一项接口保证和一个边界输入，核对命名、文档与实际行为。新增一个字段、改一种实现或跳过一次上报时，调用方对保证的理解是否仍正确。
- **例外**：专用于单个字段的接口可以按字段命名。若公开职责覆盖一组输入，文档应说清当前支持的范围。
- **证据**：
  - `codex/2026-10-21T15-02-42` Turn 3：「checkExpertTokenCountsStable 应该做成一个通用函数，叫做 checkGraphInputStable，只是现在里面只有 expert_token_counts 而已」｜raw: `/home/baowending.bwd/.codex/sessions/2026/10/21/rollout-2026-10-21T15-02-42-01a15d44-f514-7e61-8003-9d25a99ad946.jsonl`
  - `claude/e59bba96` Turn 1：「Rename the captured-buffer check to checkGraphInputStable. It currently checks expert_token_counts only; keep it simple, no registry/templates.」｜raw: `/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/e59bba96-204b-4757-979a-4f36ab1f4440.jsonl`

## R-OWN-09 在首次读取前初始化成员

- **内容**：对于有未初始化值风险的语言和类型，追到所有构造方式以及第一次读取。按字段语义使用构造参数、成员初始化、值初始化或确定先于读取的赋值。
- **为什么**：聚合体默认初始化不保证清零；某个分支只读不写（如 `report()` 里无条件读 `ep_rank`）时，行为不可预测，且很难在测试中稳定复现。
- **坏例**：
```cpp
class RtpLLmEplbMetricsCollector final {
 public:
  int64_t ep_rank;              // 未初始化
  bool    update_weights_qps;   // 未初始化
  std::vector<int64_t> gpu_loads;
};
// 某个类的成员，使用它的构造函数未给标量字段赋值
RtpLLmEplbMetricsCollector executor_collector_;
```
- **好例**：
```cpp
// 这个聚合体支持零初值。在成员声明处值初始化即可覆盖上述构造路径。
RtpLLmEplbMetricsCollector executor_collector_{};
```
- **判定**：选择一个会跳过赋值的可达分支，核对读到的值是否有定义。仅凭缺少某种初始化语法不能成立。
- **例外**：必填身份或句柄无法用零值表示时，应在允许读取前取得真实值，或明确表达尚未就绪。
- **证据**：
  - `claude/11d7031c` Turn 6：「RtpLLmEplbMetricsCollector is an aggregate with public int64_t ep_rank… primitive fields have no default member initializer… Fix: value-initialize member with {}.」｜raw: `/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/11d7031c-b168-4ece-8e6a-09c1df4c29c9.jsonl`

## R-OWN-10 资源所有者的复制和移动语义应与释放方式一致

- **内容**：C++ 类型手工管理句柄或内存时，检查编译器生成及手写的复制、移动操作会把释放责任交给谁。唯一所有者可以禁拷，可复制资源需要深拷贝或有明确语义的共享。
- **为什么**：默认拷贝是浅拷贝，两个对象析构同一指针；这类问题在扩展调用路径时才暴露，排查成本极高。
- **坏例**：
```cpp
class Allocation {
 public:
  ~Allocation() { if (ptr_) cudaFree(ptr_); }
  void allocate(size_t bytes) { ptr_ = ...; }
 private:
  void* ptr_ = nullptr;   // 拷贝后两个对象指向同一块
};
```
- **好例**：
```cpp
// 示意：接管一块已分配的显存，移动时移交释放责任
class Allocation {
 public:
  explicit Allocation(void* owned) : ptr_(owned) {}
  Allocation(const Allocation&) = delete;
  Allocation& operator=(const Allocation&) = delete;
  Allocation(Allocation&& other) noexcept : ptr_(std::exchange(other.ptr_, nullptr)) {}
  ~Allocation() { if (ptr_) cudaFree(ptr_); }
 private:
  void* ptr_;
};
```
- **判定**：构造副本或移动后再销毁两个对象，核对每份资源是否恰好释放一次。新值覆盖旧值时，一并检查旧资源的释放。
- **例外**：若所有权由成员类型正确实现，外层可以使用默认生成的操作。
- **证据**：
  - `dsh/session-c8d80a5c` Turn 1（经 agent 转述）：「`Allocation` 有裸指针 + 析构 free，但未 delete copy/move，是否存在 latent double-free；当前是否真的没有被拷贝」｜raw: `/home/baowending.bwd/.dsh/sessions/--home-baowending.bwd-new-RTP-LLM-github-opensource--/c8d80a5c-32e5-4227-8a23-dfc703aedc9a/session.v4.jsonl.zstd`

## R-OWN-11 把共同的不变量收在负责该操作的入口

- **内容**：多个调用方都必须按固定顺序执行一组动作时，检查能否由单个入口保证收尾和状态更新。把有独立用途的操作保留下来。
- **为什么**：相同的顺序约束散在多个调用点，新入口和异常路径容易漏掉收尾，也可能过早清理仍需使用的状态。
- **坏例**：
```cpp
if (!warmup) {
    monitor_->recordStep();
}
monitor_->beginStep();  // 实际只是清零；正常记录还依赖调用方补这一句
```
- **好例**：
```cpp
if (!warmup) {
    monitor_->recordStep();  // 内部先采样，再 clearRecordBuffer()
} else {
    monitor_->clearRecordBuffer();  // warmup 只清零，不推进窗口
}
```
- **判定**：检查正常返回、提前返回和独立使用者。若能指出一个可达路径会漏做必要步骤，说明它会留下什么状态。若所有路径已经正确，把合并列为可维护性建议。
- **例外**：真实调用方若只需其中一项操作，保留相应接口。例如预热只清零，正常记录则在采样后清零。
- **证据**：
  - `dsh/session-761ecd9b` Turn 31：「zeroStepCounts 和 stepCountsBuffer 应该是可以合成一个函数的？」｜raw: `/home/baowending.bwd/.dsh/sessions/--home-baowending.bwd-RTP-LLM-github-opensource--/session-761ecd9b-2f24-435e-8b68-2622832bea89/session.v4.jsonl.zstd`
  - `codex/01a15d3e-ab06-7732-ba3b-af0098e8b866`，2026-10-22 16:47:05（Asia/Shanghai），Turn 未核实，jsonl 第 14016 行：「beginStep改名成clearRecordBuffer， load_monitor_->recordStep() 包括clearRecordBuffer 然后加一个else {load_monitor_->clearRecordBuffer()} 这样更符合逻辑点」｜raw: `/home/baowending.bwd/.codex/sessions/2026/10/21/rollout-2026-10-21T14-55-50-01a15d3e-ab06-7732-ba3b-af0098e8b866.jsonl`

## R-OWN-12 按解释器契约释放由原生对象持有的 Python 引用

- **内容**：原生对象持有 Python 引用时，查实际运行时对当前线程、解释器和引用计数操作的要求。对于启用 GIL 的 CPython，可能执行 DECREF 的路径必须在对应解释器的 GIL 保护下运行。
- **为什么**：最后一次释放可能运行 Python 析构逻辑。若清理发生在线程退出、构造失败或解释器关闭期间，正常调用路径提供的条件可能已不成立。
- **坏例**：
```cpp
~Wrapper() {
  // 此例允许从未持 GIL 的原生线程析构
  graph_runner_.reset();            // runner 析构可能释放 Python 方法
  py_model_ = py::object();         // 这次赋值也可能递减引用计数
}
```
- **好例**：
```cpp
~Wrapper() {
  py::gil_scoped_acquire gil;   // 自己持 GIL；构造失败回滚复用同一段
  // 顺序：先销毁引用 Python 的 runner，再释放 py model
  generation_prefill_graph_runner_.reset();
  graph_runner_.reset();
  py_model_ = py::object();       // 在 GIL 作用域内清空持有的 Python 引用
}
```
- **判定**：定位最后一次释放，包括析构函数体结束后的成员析构。追溯正常关闭、部分构造失败和错误展开时解释器是否仍可用、依赖是否仍存活，以及线程是否具备该构建所需的执行上下文。
- **例外**：调用框架若已在所有释放路径保证正确的线程和 GIL，直接使用这项保证。采用其他运行时或自由线程构建时按对应契约核对。
- **证据**：
  - `claude/da5780f8` Turn 1：「Pay attention to actual ownership/cycles and Python GIL destruction」｜raw: `/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/da5780f8-d4c1-4cc8-90e2-2afa4fd9afc2.jsonl`
  - `codex/2026-10-22T11-01-58` Turn 3（agent 复核）：「ExpertBalancerPythonWrapper 必须自行持 GIL 释放 Python 引用，覆盖正常析构和构造失败展开」｜raw: `/home/baowending.bwd/.codex/sessions/2026/10/22/rollout-2026-10-22T11-01-58-01a1618e-eaa0-7f02-9b44-6e8b3f0af0be.jsonl`

## R-OWN-13 改接口签名时核对实际消费者和兼容约定

- **内容**：从接口声明和实际调用两端检查变更。按项目存在的入口追到绑定、包装、动态分派、测试替身和外部消费者。若接口承诺兼容，拿一条旧调用按新签名绑定实参，核对顺序、名称、默认值和结果。
- **为什么**：动态调用可能到运行时才报错。位置参数被新类型接受时，调用甚至能编译并成功返回，却把旧值解释成另一种含义。
- **坏例**：
```python
# 生产代码已改成直接读 inputs.expert_token_counts
inputs = SimpleNamespace(attention_inputs=attn, input_ids=ids)   # 测试没同步
prefill_forward.forward_prefill(v4, None, None, inputs)          # AttributeError
```
- **好例**：
```python
inputs = SimpleNamespace(
    attention_inputs=attn, input_ids=ids, expert_token_counts=None
)
```
- **判定**：同时查构造点、别名、回调和容器内取出的可调用对象。新增必填参数时，旧调用里本来就没有参数名。区分应随本次改动迁移的内部使用者，以及仍受版本兼容承诺保护的旧调用。
- **例外**：公开重载或旧字段仍在兼容期时，旧名字继续出现是预期行为。需要验证旧用法与新用法得到各自约定的结果。
- **实际案例**：`GroupSet::initialize` 的旧调用在第四个位置传 `true`。把这个位置改为 `physical_payload_bytes` 后，`true` 能转换成数值 `1`，编译通过也会把大小误设为 1 字节。
- **证据**：
  - `remote106/codex/2026-09-30T23-25-47` Turn 4（经 agent 转述）：「静默参数错位：main 的 `GroupSet::initialize` 第四参数现在是 `physical_payload_bytes`，旧 CRC 是 `bool`。遗留 `initialize(..., true)` 会编译通过却配置成 1 字节」｜raw: `11.161.48.106:/home/baowending.bwd/.codex/sessions/2026/09/30/rollout-2026-09-30T23-25-47-01a0f2eb-fd46-79f0-b34e-7692a5613953.jsonl`
  - `claude/413c0761` Turn 1：「native/Python/binding signature agreement and missed callers」；Turn 3：「`test_prefill_fast_path_cuda.py:247` was not updated for the direct-attribute-access change」｜raw: `/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/413c0761-03be-42fb-83ed-54ba68a2b04b.jsonl`
  - `claude/5269b922` Turn 1：「Main risks: newly mandatory expert_token_counts/expert_load arguments omitted by reachable callers or tests」｜raw: `/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/5269b922-a41d-49ee-8ee4-154eb4090405.jsonl`

## R-OWN-14 决策放在掌握依据的层，消费方只依赖所需结果

- **内容**：找出谁掌握做决定所需的信息，谁只需要结果。沿接口逐项核对决策的中间状态和实现细节是否影响消费方承诺的行为。
- **为什么**：相邻层各自解释同一项策略，改一次策略就要修改多个原本独立的组件。反过来，上层若猜测内部表示，也会在替换实现时分配错误的资源。
- **坏例**：
```python
class FusedMoeLayer:
    def forward(self, x, tokens, step):
        self.counts[self.layer_id] += histogram(x)
        self.tokens_window[step] = tokens.numel()   # 下层感知 step/窗口
        if step + 1 == self.window:
            self.flush_to_rank0()
```
- **好例**：
```python
class FusedMoeLayer:
    def forward(self, x):
        # 本例计算实际参与该层运算的输入，包含 padding
        self.counts[self.layer_id].copy_(histogram(x))

# 外层 unpad 后写 [step, layer, local_expert] 与 tokens_window[step]
balancer.commit_step(layer_counts, valid_tokens)
```
- **判定**：分别从两端追踪一项新增字段。下层使用它时是否掌握正确的语义，上层读取它时是否依赖某个实现的内部表示。指出删除依赖后会改变的实际行为。
- **审查可选功能时，假设明天要删除它。** 从真实入口沿调用链标出谁做决定、谁只消费结果，再列出删除开关和决策代码后还须修改的模块。逐个检查这些模块里的分支及其实际读取的字段。例如计价模块已经算出最终金额，支付网关仍按券种分支，就追到支付接口核对：券种究竟会改变哪项支付请求？若两条路径提交相同的金额和参数，指出可以删掉的判断。文件数量本身不能证明职责扩散。
- **实际案例**：RTP-LLM PR #1790（`fe36baa064`）里，`distribute/host_bootstrap.py::prepare_host` 用入选机器更新并行配置，`start_server.py::main` 随后进入原有模型配置流程。审查模型层时可以问：删掉整机筛选，权重加载是否仍须用最终的并行配置验证权重？这项校验仍然成立，应留在模型层。让模型加载器识别“哪台机器因为坏卡被剔除”才会引入对筛选策略的依赖。
- **例外**：消费方的公开契约若依赖某个细节，应保留相应数据。例如支付渠道要求提交补贴凭证，网关就需要凭证。显式约定由调用方管理的输出缓冲同理。
- **证据**：
  - `codex/2026-10-16T12-03-25` Turn 53：「每层肯定不需要知道真实 token 数和 step 计数的，因为 padding token 也真实参与 moe 计算，它只负责写 [layer,local_expert] 的窗口，然后外面 unpad 以后写入 balancers 才是 [step, layer, xxxx] 的统计数据和 [step] 的 token 计数」｜raw: `/home/baowending.bwd/.codex/sessions/2026/10/16/rollout-2026-10-16T12-03-25-01a142e1-03e2-7c80-91f7-a6ccae9f6a25.jsonl`
  - `codex/01a1c90c-cc18-7063-8df2-30bdbddc6977`，2026-11-12T09:59:00.433Z（UTC），Turn 未核实，第 5780 行：「gatherSpecSamplerInput应该考虑的是怎么给sampler一个通用的输入；内部字段应该sampler forward里面临时申请，不要放在smapler_input里面」｜raw: `/home/baowending.bwd/.codex/sessions/2026/11/11/rollout-2026-11-11T13-20-21-01a1c90c-cc18-7063-8df2-30bdbddc6977.jsonl`
  - `codex/01a1f28b-91db-7bb0-9891-0bb77fc96ebb`，2026-11-24T07:12:42.799Z（UTC），Turn 未核实，第 7081、7107 行：「我看他要每个地方都改一下，这个功能到时候都不好删除啊」「就是我不能理解为啥要修改model_loader / rtp_llm/models_py这些地方的」｜raw: `/home/baowending.bwd/.codex/sessions/2026/11/19/rollout-2026-11-19T14-43-15-01a1f28b-91db-7bb0-9891-0bb77fc96ebb.jsonl`

## R-OWN-15 核对承诺同一行为的各条可达路径

- **内容**：确定哪些入口、角色和实现对同一输入承诺同一结果。沿各自的实际分派、默认实现和回退路径检查这项保证，允许不同实现用各自的方法履约。
- **为什么**：两条路径在不同资源状态下可能选中不同实现。只看专用实现或配置字段，容易遗漏切换后实际执行的分支。
- **坏例**：
```cpp
if (group == Group::FULL) {
  detachSubtree(node);          // 摘整棵子树
} else {                        // SWA：只清自己这一组
  dropResource(node, group);    // 未检查同节点其他组的在途操作
}
```
- **好例**：
```cpp
// 失效语义与组类型无关：都摘整棵子树，资源统一交给回收器
// 注：以下符号来自内源仓库/评审中的 PR（github-opensource HEAD 未合入），仅示意形态
detachSubtree(node);
markInFlightOperationsInvalid(node);   // LOAD_PENDING / LOADING / DEMOTING
tree_->reclaimDetachedNodes(affected); // 每个节点等自己的 GroupSet 全回 IDLE
```
- **实际案例**：在 `872d8f617a67` 的普通 MTP 中，graph 关闭时不会创建专用 commit wrapper，`runDraftPrefillForward` 会回退到 `draft_model_`。只查专用 wrapper 的配置会漏掉实际启用统计的路径。
- **判定**：固定一项对外保证，找出会改变分派的条件。逐条追到真正执行操作的位置，比较其结果或副作用。报告缺口时写明受影响的条件和入口。
- **例外**：不同角色或数据布局可以有各自的契约。比较之前先核对调用方实际依赖的行为及其范围。
- **证据**：
  - `remote106/codex/2026-10-10T14-39-48` Turn 7：「等下，FULL 和 SWA，对于处理单个节点应该会有同样的问题吧，这边 crc 校验希望删除，但是可能有淘汰 copy 正在拷贝 / pending load 正在等待，无法直接删除」｜raw: `11.161.48.106:/home/baowending.bwd/.codex/archived_sessions/rollout-2026-10-10T14-39-48-01a1248a-092d-7a31-b4bf-192201c5ece4.jsonl`
  - `codex/01a15d3e-ab06-7732-ba3b-af0098e8b866` 2026-10-22 17:43:56（Asia/Shanghai），Turn 未核实，行 425：「有实际确认过draft和target model都会汇报监控，且commit阶段不汇报，只汇报prefill/ decode target verify / decode draft propose吗」｜raw: `/home/baowending.bwd/.codex/sessions/2026/10/22/rollout-2026-10-22T17-19-12-01a15d3e-ab06-7732-ba3b-af0098e8b866_01a162e8-4734-7e01-810d-2803cb609841.jsonl`
