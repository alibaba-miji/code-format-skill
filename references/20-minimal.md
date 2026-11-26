# 20 · 最小实现（R-MIN）

> 审查新增分支、包装、错误处理与并发机制时，沿受支持的调用路径说明它会改变哪项行为。

## R-MIN-01 不加过度校验、防御与回退

- **内容**：在外部输入、配置等边界建立约束。内部判断要能指出在哪个受支持入口、哪种状态下会改变结果，尤其要逐项看 `and`、`or` 中的条件。经过状态修改、异步调用或独立的信任边界后，重新确认上游约束是否仍然成立。
- **为什么**：一个分支整体可达，其中某项仍可能恒真或恒假。重复判断让读者误以为调用方能传入这种状态，还可能产生额外的热路径开销，例如每次 forward 都执行 `zero_()`。误删有效条件则会改变正常分派，甚至造成越界访问。
- **坏例**：
```cpp
// 内部函数：上游已保证 ids 非空、count>0、buffer 已分配
void recordStep(const int64_t* ids, size_t count) {
  if (ids == nullptr) return;
  if (count == 0) return;
  if (count > kMaxCount) count = kMaxCount;   // 静默截断
  if (!buffer_.defined()) return;
  buffer_.zero_();                            // 每步多一次 GPU 操作
  try { launch(ids, count); } catch (...) { /* 吞掉 */ }
}
```
- **好例**：
```cpp
// 前置条件写在头文件；唯一入口断言一次，热路径直接依赖
RTP_LLM_CHECK_WITH_INFO(counts.numel() == layers_ * experts_, "expert counts shape mismatch");
void recordStep(const int64_t* ids, size_t count) {
  RTP_LLM_CHECK(count <= kMaxCount);   // 违反即 fail-fast，不静默截断
  launch(ids, count);                  // writer 契约保证全覆盖写，不补 zero_()
}
```
- **判定**：从所有受支持的入口追到判断点，核对参数在哪里构造或校验，期间是否被重写、异步更新或经回调重新传入。对 `A && B` 找 `A` 为真时 `B` 改变结果的输入；对 `A || B` 找 `A` 为假时的对应输入。也对 `A` 做同样检查，注意短路是否保护后续访问。若所有入口都已排除一种取值，且中途状态不会变化，只精简已证明冗余的部分。某一入口或状态转移尚未核实时，标为「可达性待核实」，并注明缺哪段证据。
- **例外**：保留外部输入校验，以及保护越界访问、空指针解引用、跨 rank 失步的可达条件。例如 BlockTreeLoader 构造 DEVICE 来源的描述符时将 `source_node` 设为 `nullptr`，复核 `source_tier != DEVICE` 时须追到它保护的节点访问。
- **实际案例**：packed mask 的两个生产入口分别检查 logits 布局、词表范围和任务尺寸，并在内部构造 mask 与行映射，launcher 可以去掉相应的重复检查。上游入口仍应拒绝真实的词表范围错误，kernel 仍须跳过负数行号及 `dense_to_packed` 映射值 `-1`。[packed mask 核对记录](90-feedback.md#已核对案例packed-mask-内部入口的重复校验)
- **证据**：
  - `codex/2026-10-20T18-16-41` Turn 1：「注意代码保持简洁，不要有过度校验和防御」｜raw: `/home/baowending.bwd/.codex/archived_sessions/rollout-2026-10-20T18-16-41-01a158d0-31db-7442-a5a7-c2324f46f132.jsonl`
  - `claude/11d7031c` Turn 1：「Do not invent unsupported call sites, add defensive checks for impossible configs… The user explicitly wants simple code and no excessive validation.」｜raw: `/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/11d7031c-b168-4ece-8e6a-09c1df4c29c9.jsonl`
  - `dsh/session-761ecd9b` Turn 1：「每个地方都 if(expert_load_monitor_) abort 也不合理，外面反正本来就会 abort 的，expert_load_monitor_ 有啥错 record 自己爆出来，别在这里 abort」（同一指令在 `dsh/session-456f2d53` 另一次下达，见 R-MIN-09）｜raw: `/home/baowending.bwd/.dsh/sessions/--home-baowending.bwd-RTP-LLM-github-opensource--/session-761ecd9b-2f24-435e-8b68-2622832bea89/session.v4.jsonl.zstd`
  - `remote106/codex/2026-10-10T14-39-48` Turn 7：「FULL 和 SWA……这边 crc 校验希望删除，但是可能有淘汰 copy 正在拷贝 / pending load 正在等待」——删条件前必须先证明它守的不变量｜raw: `11.161.48.106:/home/baowending.bwd/.codex/archived_sessions/rollout-2026-10-10T14-39-48-01a1248a-092d-7a31-b4bf-192201c5ece4.jsonl`

  - `remote106/codex/2026-10-13T13-02-15` Turn 1（经 agent 转述）：「不对啊哥，看上去分段没有任何优势啊」；Turn 2：「支持删除，并且也更新下 pr，把这段删了吧」｜raw: `11.161.48.106:/home/baowending.bwd/.codex/sessions/2026/10/13/rollout-2026-10-13T13-02-15-01a133a3-cd6f-7a80-9ef9-35e987cc108c.jsonl`
  - `remote106/codex/2026-10-14T19-24-10` Turn 1（经 agent 转述）：「这个行为他会改掉，我们只需要考虑……的防护逻辑即可」——依赖方承诺修的地方本方不再兜底｜raw: `11.161.48.106:/home/baowending.bwd/.codex/sessions/2026/10/14/rollout-2026-10-14T19-24-10-01a13a27-d372-7b72-bcdc-e5c2d901a970.jsonl`
  - `codex/01a1c90c-cc18-7063-8df2-30bdbddc6977` 第 2451 行（Turn 未核实）：「有些没用的校验全部删了吧，你扫一下应该我看都是没有路径会走到的」。两个生产入口、保留条件及增量补丁见上述核对记录。｜raw: `/home/baowending.bwd/.codex/sessions/2026/11/11/rollout-2026-11-11T13-20-21-01a1c90c-cc18-7063-8df2-30bdbddc6977.jsonl.zst`
  - `codex/01a211cd-fdf8-7252-bf92-8f096efabd7f` 第 2959 行（2026-11-26 06:33:01 UTC，Turn 未核实）：「仔细思考每个if中的条件是否有意义，有些对于分支有要求，但是实际上游链路根本不会传或者上游已经判断过的，不应该重复判断」。｜raw: `/home/baowending.bwd/.codex/sessions/2026/11/25/rollout-2026-11-25T16-24-02-01a211cd-fdf8-7252-bf92-8f096efabd7f.jsonl`

## R-MIN-02 禁止静默 fallback 与吞异常

- **内容**：对每个失败分支，追到使用结果的调用方。操作未完成时，返回的状态、错误或降级结果应符合接口约定，让需要采取行动的调用方能够区分它们。错误信息保留定位所需的上下文。
- **为什么**：读取失败时填 0，调用方可能把数据缺失解释成确实没有工作量。即使写了日志，依赖返回值的决策仍会出错。
- **坏例**：
```cpp
try {
  consumeWindow();
} catch (const std::exception&) {
  samples = 0;            // 静默跳过本窗口，调用方无从得知
}
```
```python
# 不良错误信息：用户不知道实际值、限值是多少、该改哪个配置
raise ValueError("CRC payload too large")
```
- **好例**：
```cpp
try {
  consumeWindow();
} catch (const std::exception& e) {
  RTP_LLM_LOG_ERROR("EPLB window consume failed (window=%zu, step=%lld): %s",
                    window.size(), step_, e.what());
  throw;                  // 或返回明确错误状态，由边界决定策略
}
```
```python
MAX_PAYLOAD = (1 << 32) - 1
raise ValueError(f"CRC payload {payload} exceeds the limit {MAX_PAYLOAD}")
```
- **判定**：检查捕获、重试和默认值改变了什么结果，以及调用方据此会执行什么操作。若观察到的只是 I/O 失败，沿路径检查它能否被误判为数据损坏，触发删除或隔离。
- **例外**：对于允许丢样本或尽力而为的任务，按约定处理失败。指标、日志和错误返回各有消费者，按实际需要选用。
- **证据**：
  - `claude/a8ab1566` Turn 1：「是否有…重复校验、异常吞噬、静默 fallback」｜raw: `/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/a8ab1566-478b-477f-b7a0-b1a3f858d32f.jsonl`
  - `claude/bbb141fb` Turn 1：「No style nits, speculative generic defense, future unimplemented policy features」｜raw: `/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/bbb141fb-d1cf-4129-99a9-05483c8ecaa2.jsonl`

## R-MIN-03 删死代码前查清所有受支持的入口

- **内容**：确认参数、成员或分支已失去作用后，一并移除只为它存在的判断和注释。查构造点、调用点和动态入口，也核对仓外调用方或旧版数据是否仍通过这个接口。
- **为什么**：不可达的分支让读者误判哪些状态仍需支持。只按仓内搜索结果删除对外参数，又可能破坏旧客户端。
- **坏例**：
```cpp
// warm_up_ 恒为 false：12 处分支永不可达，注释还停留在旧架构
MtpExecutor(..., bool warm_up = false) : warm_up_(warm_up) {}
if (warm_up_) { reporter_ = nullptr; }          // 死
if (warm_up_) { cache_manager_ = nullptr; }     // 死，且后续无条件解引用会崩
```
- **好例**：
```cpp
MtpExecutor(...);                        // 参数、成员、12 处分支、过期注释一并删除
if (model_input.is_fake_stream) { ... }  // 已有语义承担者，行为不变
```
- **判定**：列出能给字段赋值或影响分支的入口，确定可以删到哪一层。若删的是内部参数，上游仍允许传入旧字段，说明兼容处理保留在哪里。
- **例外**：接口、序列化或 ABI 兼容期仍在生效时，保留契约要求的部分。
- **证据**：
  - `codex/2026-10-22T11-30-49` Turn 6：「mtpexecutor 也改一下，发现我们修改了 warmup 相关的逻辑，但是 warmup 完全没用，不如直接删了」｜raw: `/home/baowending.bwd/.codex/sessions/2026/10/22/rollout-2026-10-22T11-30-49-01a161a9-52d2-77e3-8565-097763229970.jsonl`
  - `dsh/session-51eaaf85` Turn 1：「看下 rtp_llm/cpp/normal_engine/speculative/MtpExecutor.cc，这个 warm_up_ 真的有用吗？」｜raw: `/home/baowending.bwd/.dsh/sessions/--home-baowending.bwd-RTP-LLM-github-opensource--/session-51eaaf85-df6c-4828-bc51-aa9ab4f0a5f1/session.v4.jsonl.zstd`
  - `claude/775dda99` Turn 1：「removal of MtpExecutor's unused warm_up argument/member and associated branches while preserving currently reachable behavior」｜raw: `/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/775dda99-310c-4cda-9cc7-7cbf04f91e3e.jsonl`

## R-MIN-04 包装层应承担可以指出的职责

- **内容**：沿一次完整操作检查包装层提供了什么，包括资源释放、协议适配、稳定的公开入口和调用顺序约束。若删去一层后这些行为都由现有入口保证，指出可以直接调用的接口。
- **为什么**：成对接口靠调用方自觉维持顺序，early return 就会漏调；为拿内部 buffer 多开 getter，会让同一份状态出现多个入口。历史实例：`ExpertLoadStepGuard`、`begin/finish_backend_record` 都被要求删除。
- **坏例**：
```cpp
{
  ExpertLoadStepGuard guard(expert_load_monitor_);   // 此处已由 recordStep 完成收尾
  outputs = forward(...);
}
```
```python
scratch = begin_backend_record()   # zero_ + 返回私有 buffer
backend(..., scratch)
finish_backend_record()            # 再 copy/add 回公开 tensor
```
- **好例**：
```cpp
if (!inputs.warmup) {                              // warmup 由调用方跳过
  expert_load_monitor_.recordStep();               // 裸调用；窗口/清零在内部
}
backend(..., expert_load.expert_token_counts);    // 公开 tensor 直接 int32 累加
```
- **判定**：比较调用方在成功、提前返回和异常时要做的事。拆成两个方法后，若每个调用者都必须补同一条收尾调用，检查资源所有者能否保证收尾。
- **例外**：作用域守卫即使只有一个调用点，也可能保证锁释放或事务回滚。若操作确实跨越外部回调，两阶段接口可以保留，只需明确谁负责完成或取消。
- **证据**：
  - `codex/2026-10-19T11-49-38` Turn 7：「然后不要 ExpertLoadStepGuard，这个我理解没有用」；Turn 8：「直接裸调用 expert_load_monitor_ 更好吧」｜raw: `/home/baowending.bwd/.codex/sessions/2026/10/19/rollout-2026-10-19T11-49-38-01a15247-7b12-7f22-a074-033777c9fae0.jsonl`
  - `dsh/session-51eaaf85` Turn 10：「为啥不是直接把那个 tensor 传进去，还要搞个 begin/finish，没懂啥意思」｜raw: `/home/baowending.bwd/.dsh/sessions/--home-baowending.bwd-RTP-LLM-github-opensource--/session-51eaaf85-df6c-4828-bc51-aa9ab4f0a5f1/session.v4.jsonl.zstd`

## R-MIN-05 按阻塞约束和可验证的收益选择同步或异步

- **内容**：检查调用线程能否等待、哪些工作必须并行，以及完成和失败由谁处理。串行执行已满足契约时，为收益主张找依据，再判断是否值得增加队列、线程或状态。
- **为什么**：交给后台工作者会延长对象和任务的寿命。调用方退出时，后台可能仍在写入、等待或持有资源。反过来，在事件循环里同步等待由该循环驱动的操作也可能无法完成。
- **坏例**：
```cpp
// 此窗口允许暂停采样，消费也无并发要求，却引入双缓冲与后台线程
async_copy(window, staging[buf_idx], ev[buf_idx]);
consumer_.enqueue([this, buf_idx] { reduce(staging[buf_idx]); });
buf_idx ^= 1;
```
- **好例**：
```cpp
// 同步 D2H；消费期间 CPU 侧暂停采样，单窗口足够
if (sampling_) { window.row(samples++).copy_(step_counts); }   // copy_ 而不是重绑定
if (samples == capacity) {
  const auto host = window.cpu();   // 同步，失败即暴露
  report(reduce(host));
  samples = 0;
}
```
- **判定**：沿实际调度路径检查谁生产、谁等待、谁能推进工作，以及取消或关闭时谁接管剩余操作。若改异步的理由是改善吞吐或延迟，用能区分两种实现的测量核对。
- **例外**：事件循环的非阻塞约定或必须并发推进的协议，本身就能说明异步的必要性。案例中的暂停采样只适用于明示允许漏采的统计。
- **证据**：
  - `codex/2026-10-20T18-16-41` Turn 1：「把 d2h 这一步改成同步，避免因为异步引入更多的操作」｜raw: `/home/baowending.bwd/.codex/archived_sessions/rollout-2026-10-20T18-16-41-01a158d0-31db-7442-a5a7-c2324f46f132.jsonl`
  - `codex/2026-10-16T14-40-50` Turn 1：「不用双缓冲，消费的时候不让计数器增加/写 buffer 就行，这个是统计，不用非常严格」（同一指令也见 `14-33-06`）｜raw: `/home/baowending.bwd/.codex/sessions/2026/10/16/rollout-2026-10-16T14-40-50-01a14371-2226-7e70-ae9e-d7fd52f24658.jsonl`
  - `claude/a8ab1566` Turn 1：「D2H 改为同步，删除异步额外操作」｜raw: `/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/a8ab1566-478b-477f-b7a0-b1a3f858d32f.jsonl`

## R-MIN-06 先核对已有通道能否承载新增数据

- **内容**：从数据的生产者追到使用者，比较现有参数和新增通道的所有者、传递时机和生命周期。如果现有调用已能提供同一份数据，检查新增注册、绑定或查询带来了哪项能力。
- **为什么**：同一份状态走两条路，调用方就可能在换实例或重载后读到旧值。需要跨越不同生命周期时，硬塞进一次调用的参数也会丢失信息。
- **坏例**：
```python
class FusedMoeExecutor:
    supports_expert_load_monitor = True          # 能力声明，与实现重复
    def forward(self, x, expert_load=None):
        if self.supports_expert_load_monitor:
            try:
                record(expert_load, x)
            except Exception:                    # 吞掉一切
                pass
```
```cpp
// 只为传一个 buffer 新增初始化期绑定 API
void PyWrappedModel::bind_expert_load_monitor(py::object py_eplb) {
  for (auto& layer : layers_) layer->bind_counts(counts_[layer->id()]);
}
```
- **好例**：
```python
def forward(self, x, expert_load=None):
    # 此调用协议用 None 表示本次不采样
    if expert_load is not None:
        record(expert_load, x)
```
```cpp
struct PyModelInputs {
  torch::Tensor input_hiddens;        // 真实字段名（OpDefs.h）
  torch::Tensor expert_token_counts;  // undefined = 本路径不计数（复用既有结构，不新增 optional）
};
```
- **判定**：检查重建、重载和切换实现时两条通道是否需要同步更新。若存在可选输入，分别核对「本次未请求」和「实现不支持」是否会引发不同的调用方行为。
- **例外**：能力协商、跨进程传输或独立订阅有单独的消费者和生命周期时，可使用独立接口。
- **证据**：
  - `codex/2026-10-19T11-44-39` Turn 5：「看上去只是为了做 buffer 的传递？那为啥不放在 pymodelinput 里？」（同一指令在 `11-49-38`/`11-49-52` 也出现，见 R-OWN-04/R-OWN-07）｜raw: `/home/baowending.bwd/.codex/sessions/2026/10/19/rollout-2026-10-19T11-44-39-01a15242-e9c6-7b63-bb1e-b41e57b1ce04.jsonl`
  - `claude/8dad743d` Turn 1：「remove all Python `supports_expert_load_monitor` capability declarations/checks… Pass existing optional expert_load/count arguments to kernels without a capability registry or defensive exception swallowing.」｜raw: `/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/8dad743d-7842-4885-b5fa-f1f9d9e37876.jsonl`
  - `codex/2026-10-20T18-16-31` Turn 1：「模型层也参考 deepinfer，把一些 expert 统计放到现有 kernel 的参数里」｜raw: `/home/baowending.bwd/.codex/archived_sessions/rollout-2026-10-20T18-16-31-01a158d0-0b93-7f33-883f-38316fb5db9c.jsonl`

## R-MIN-07 最小改动，不顺手引入框架或抽象

- **内容**：优先用具体改法解决具体问题。静态关系可以直连时，避免为它增加注册表、模板、插件、事件总线、锁或抽象层。现有结构确实无法满足需求时，可以替换冲突部分，避免叠加兼容层。行为修复与无关重构分开提交见 R-WRK-02。对新增状态、包装类型、重试、缓存、校验或异常捕获，先假设撤掉这一处。指出一个受支持的输入和调用路径，说明删掉后哪项结果、资源开销或失败处理会变化。沿调用链核对现有机制已经覆盖了什么。代码行数和调用点数量只帮助定位，不能证明机制多余。
- **为什么**：单个静态调用经过注册表，需要额外的注册、查找和初始化。重复处理同一次失败会放大重试次数，只包装已有结果会让每个调用点多一层拆解。反过来，外层若负责换节点或重放整个事务，删掉它会直接丢失恢复能力。
- **坏例**：
```python
MONITOR_REGISTRY = {}
def register_monitor(name):
    def deco(cls):
        MONITOR_REGISTRY[name] = cls
        return cls
    return deco

@register_monitor("router")
class RouterMonitor: ...
```
- **好例**：
```python
def make_monitor(moe_cfg, params):
    if params.eplb_config.report_interval <= 0:
        return None
    return ExpertLoadMonitor(moe_cfg, params)   # 一个工厂函数足够
```
- **判定**：逐个比较撤掉该机制前后的行为。两层重试要核对错误类型、重试对象及范围（单次 RPC、换节点或整个事务）；缓存要核对复用的资源、重复构建代价和失效条件。若已有处理在相同输入和时序下产生相同结果，说明可以删哪一层；只查到部分调用方或无法确认性能代价时，把缺口写明。
- **例外**：第二个真实调用方可以成为提取公共抽象的理由。即使只有一个调用方，也应保留能独立完成恢复或避免重复开销的机制。
- **实际案例**：调度 RPC 的两种返回包装只分别承载已有 protobuf 和无字段的传输失败，移除后调用方仍能区分业务拒绝与传输错误。换备端则有独立作用，真实双服务用例验证了主端传输失败可由备端完成，业务拒绝保留原因为终态。缓存也可能必要，例如 all-rank profiling 连续请求复用同一个 RPC pool 和 completion thread，改成每次构造都会重建这些资源。[主备 RPC 对照](90-feedback.md#已核对案例历史修复的结果类型与真实主备测试)
- **证据**：
  - `claude/e59bba96` Turn 1：「keep it simple, no registry/templates.」｜raw: `/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/e59bba96-204b-4757-979a-4f36ab1f4440.jsonl`
  - `claude/11d7031c` Turn 7：「No per-request pool, no registry, no new locks.」｜raw: `/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/11d7031c-b168-4ece-8e6a-09c1df4c29c9.jsonl`
  - `claude/6c0996cf` Turn 1：「No style nits or generic defensive checks.」｜raw: `/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/6c0996cf-276e-421d-a295-a4ead317536f.jsonl`
  - `codex/01a1819f-6539-78d3-bd42-95404cd46406` 第 2022 行（Turn 未核实）：「我们的fix和`3738ed3774` 哪个更优雅？」。历史方案、两个调用点和三种主备结果见上述核对记录。｜raw: `/home/baowending.bwd/.codex/sessions/2026/10/28/rollout-2026-10-28T16-27-49-01a1819f-6539-78d3-bd42-95404cd46406.jsonl.zst`
  - `codex/01a1a052-cad4-7752-8248-211e25971f3b` 第 5713 行（Turn 未核实）：「而且用完销毁也太奢侈了吧」。`8d18196ebf` 将 BroadcastManager 随服务复用，覆盖重复请求、并发首次创建和创建失败后的重试。｜raw: `/home/baowending.bwd/.codex/sessions/2026/11/03/rollout-2026-11-03T15-32-22-01a1a052-cad4-7752-8248-211e25971f3b.jsonl.zst`
  - `codex/01a211cd-fdf8-7252-bf92-8f096efabd7f` 第 2959 行（2026-11-26 06:33:01 UTC，Turn 未核实）：「前两条补到已有规则，后两条单独成卡，让后面多模型 review 的时候能用上，加上实际的case」。第 2952 行所列第二条为核对撤掉新增机制后的具体故障。｜raw: `/home/baowending.bwd/.codex/sessions/2026/11/25/rollout-2026-11-25T16-24-02-01a211cd-fdf8-7252-bf92-8f096efabd7f.jsonl`

## R-MIN-08 拆分与抽象必须有可验证收益

- **内容**：提取函数、拆文件或合并参数时，指出调用方少维护了哪段逻辑，或哪个边界变得可以单独构建、测试或理解。
- **为什么**：参数表搬家不减少任何耦合，还会引入参数错位风险；纯 move 的大 diff 让 review 更难。
- **坏例**：
```cpp
struct CrcLaunchArgs { void* a; size_t b; /* …18 个字段… */ };   // 参数表搬家
launchCrc32cBatched(args.a, args.b, /* …仍是 18 个参数… */);
```
- **好例**：
```cpp
// Impl 已持有 12 个固定成员，只暴露真正变化的 4 个
cudaError_t launchCrc(size_t count, size_t msg_offset, bool store, void* const* host_records);
```
- **判定**：对照拆分前后的调用点和依赖。参数只是逐项搬进再取出，或同一段调用顺序仍须到处重复时，给出一处具体的遗留问题。
- **例外**：参数组合本身具有业务语义或不变量时，即使只有一个调用方，把它们放进同一类型也有价值。
- **证据**：
  - `dsh/session-c8d80a5c` Turn 1（经 agent 转述）：「`CrcBlockCopy.cu` 969 行是否值得拆文件（给出理由，不要为了拆而拆）」「抽 helper/参数 struct 是否安全、能减少什么风险」｜raw: `/home/baowending.bwd/.dsh/sessions/--home-baowending.bwd-new-RTP-LLM-github-opensource--/c8d80a5c-32e5-4227-8a23-dfc703aedc9a/session.v4.jsonl.zstd`

## R-MIN-09 在有权决定失败影响范围的边界处理错误

- **内容**：组件报告操作失败时保留原因。若它直接结束整个进程，追到负责请求、任务或进程生命周期的边界，核对什么状态使继续运行不安全，以及谁有权作出终止决定。
- **为什么**：把一次局部失败升级为进程退出，会中断其他请求，也使外层失去重试、隔离或降级的机会。
- **坏例**：
```cpp
if (expert_load_monitor_) {
  try { expert_load_monitor_->recordStep(warmup); }
  catch (...) { std::abort(); }   // 组件内杀进程，且丢失原因
}
```
- **好例**：
```cpp
// 将原始监控错误交给引擎的失败处理边界
expert_load_monitor_.recordStep();
```
- **判定**：读实际的断言、异常处理器和运行配置，区分它们是向上返回还是立即终止。指出受影响的其他工作、仍可执行的恢复操作，以及失败后继续运行是否安全。
- **例外**：完整性已破坏、继续执行可能损坏数据时，遵循系统已有的终止策略。在无法安全向上交还控制的现场立即停止也可以是契约的一部分。
- **证据**：
  - `dsh/session-456f2d53` Turn 1：「每个地方都 if(expert_load_monitor_) abort 也不合理，外面反正本来就会 abort 的，expert_load_monitor_ 有啥错 record 自己爆出来，别在这里 abort」｜raw: `/home/baowending.bwd/.dsh/sessions/--home-baowending.bwd-RTP-LLM-github-opensource--/session-456f2d53-cae2-4086-94ee-d14f3ef32b16/session.v4.jsonl.zstd`

## R-MIN-10 按日志的用途和频率决定记录点

- **内容**：从日志的使用者出发，说明这一条能回答什么问题。相同事件已经在合适层记录时，检查重复日志及其专用去重状态是否还提供额外信息。
- **为什么**：高频成功日志既占用 I/O，也会淹没故障线索。审计、计费或问题复现有时需要成功记录，删掉它们也会破坏调用方依赖的证据。
- **坏例**：
```cpp
if (result != CrcCopyStatus::OK) { RTP_LLM_LOG_WARNING("...failed..."); }   // 循环里已打过
if (result == CrcCopyStatus::OK) {                                  // 成功也打
  const unsigned bit = 1u << static_cast<unsigned>(operation);
  if (!(logged_operations_.fetch_or(bit, std::memory_order_relaxed) & bit)) {
    RTP_LLM_LOG_INFO("...completed...");
  }
}
```
- **好例**：
```cpp
// 失败在产生处记录一次（含 block index / tier / status）
// 成功路径静默；删除 logged_operations_ 与 <atomic> 依赖
```
- **判定**：对照实际排障或审计需求、事件频率和已有记录。多实例记录需要区分来源时，先检查现有日志上下文是否已经包含身份。
- **例外**：每个参与方的独立结果、审计流水或生命周期变更，各自可能值得记录。先确认消费者，再决定能否合并或采样。
- **证据**：
  - `remote106/codex/2026-10-12T19-28-32` Turn 1：「ok 不需要加日志，非 ok 应该上面循环里也加过了，这两段应该没必要」｜raw: `11.161.48.106:/home/baowending.bwd/.codex/sessions/2026/10/12/rollout-2026-10-12T19-28-32-01a12fdf-184f-7a90-9d06-d076dd59a89a.jsonl`

## R-MIN-11 按接口约定区分正常结果与异常

- **内容**：普通分支已经由返回值或状态表达时，检查额外的抛出和捕获是否改变了调用方能区分的结果。沿用当前语言和接口约定的控制流，避免宽泛捕获同时掩盖真实故障。
- **为什么**：同一个异常既表示预期结果又表示内部故障时，调用方可能把失败当作一次正常跳过。
- **坏例**：
```cpp
void updatePlan(Plan& plan) {
  try {
    plan.apply();             // apply 用 throw 表示「本步无需变更」
  } catch (const NoChange&) {
    return;                   // 正常分支用异常表达
  }
}
```
- **好例**：
```cpp
// 正常分支用返回值表达；异常只留给真正的失败
enum class ApplyResult { kApplied, kNoChange };
ApplyResult apply(Plan& plan);   // 调用方显式处理 kNoChange
```
- **判定**：找一个预期结果和一个真实故障，分别追到处理者。若二者会落入同一条提前返回路径，指出具体被吞掉的错误。
- **例外**：语言或库把某个异常定义为正常结束信号时，遵循协议，例如 Python 迭代器的 `StopIteration`。仅在边界确实需要另一种表示时转换。
- **证据**：
  - `remote106/codex/2026-10-13T10-10-43` Turn 28（经 agent 转述）：「我们这个操作应该是完全不会引入异常路径的，不要加 try catch 这些迷惑的东西」｜raw: `11.161.48.106:/home/baowending.bwd/.codex/sessions/2026/10/13/rollout-2026-10-13T10-10-43-01a13306-5c7d-7e21-9b4a-2d5e6f7a8b90.jsonl`
