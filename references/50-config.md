# 50 · 配置与契约边界（R-CFG）

> 改动涉及配置解析、跨模块传值或容量限制时，沿调用方提供的输入追到使用这些值的代码。

## R-CFG-01 在配置生效的范围内沿用同一份解析结果

- **内容**：先明确这项配置对哪个组件、进程或请求生效，以及何时读取。多个来源共同决定同一个值时，在负责解析的入口解决优先级，追踪消费者实际使用的结果，包括路径上真实存在的序列化或进程边界。
- **为什么**：下游自行重读环境可能覆盖调用方的显式传值，序列化漏字段则会让远端进程默默使用默认值。
- **坏例**：
```python
def use_crc():
    return os.getenv("ENABLE_CRC", "1") == "1"  # 忽略外层已经解析的 enable_crc
```
- **好例**：
```cpp
// CRC 工厂接收启动配置中已经解析并传到当前进程的字段。
bool crcEnabled() const { return enable_crc_; }
```
- **判定**：从真实入口传入与回退值不同的值，核对它在最终消费点仍然生效。有多个来源时让两者给出不同值，才能检验优先级。
- **例外**：进程本地配置可以在该进程自己的入口读取。支持热更新或请求级覆盖的系统要按约定的更新和覆盖时机追踪。
- **证据**：
  - `codex/2026-10-19T11-06-48` Turn 2：「测试完之后改一下 enable_crc，不要直接从环境变量读，和其他参数一样在最外面配置，一层层传进来，并且校验 enable_crc 链路实现完全」｜raw: `/home/baowending.bwd/.codex/archived_sessions/rollout-2026-10-19T11-06-48-01a15220-431e-7411-a9e4-4c65ff05459e.jsonl`
  - `codex/2026-10-19T10-40-16` Turn 7：同一条要求（archived 会话）｜raw: `/home/baowending.bwd/.codex/archived_sessions/rollout-2026-10-19T10-40-16-01a15207-f8b8-7272-aab3-cb92ad9d4a6d.jsonl`

## R-CFG-02 在前置条件可能失效的边界验证它

- **内容**：找出一项操作实际依赖的前置条件，核对接口如何表达它，以及哪些调用方已经保证它。如果值可在检查后被替换、修改，或跨入新的信任边界，应在第一次依赖该条件之前重新建立保证。
- **为什么**：只验证过旧对象，不能保证当前对象有效。已经由类型或不可变构造保证的条件再检查一遍，则会让人误以为这里仍有失败路径。
- **坏例**：
```cpp
// 允许调用方更换输入缓冲，重放却继续写入旧图绑定的地址。
void forward(const PyModelInputs& inputs) { graph_runner_->forward(inputs); }
```
- **好例**：
```cpp
// 本例接收外部缓冲，对照当前实例捕获的对象进行检查。
const auto& captured = graph_instances_[idx].mem_hold_.py_model_inputs_.expert_token_counts;
RTP_LLM_CHECK_WITH_INFO(
    inputs.expert_token_counts.data_ptr() == captured.data_ptr()
        && inputs.expert_token_counts.sizes() == captured.sizes(),
    "expert counts buffer changed since graph capture");
graph.replay(inputs);
```
- **判定**：针对每个条件给出一个受支持的调用路径和会破坏条件的输入，或指出上游保证为何一直有效。昂贵且必要的校验可以在数据进入时完成，前提是随后使用的仍是同一份有效数据。
- **例外**：对可信调用方明确约定的前置条件，可以由类型、接口契约或构造过程保证。接口承担拒绝非法输入的责任时，文档本身无法履行这个责任。
- **证据**：
  - `dsh/session-761ecd9b` Turn 10：「如果 step_expert_token_counts 在外面传进去的话，我觉得有必要的是 graph runner 里面确认一下地址和 capture 时候是一致的」｜raw: `/home/baowending.bwd/.dsh/sessions/--home-baowending.bwd-RTP-LLM-github-opensource--/session-761ecd9b-2f24-435e-8b68-2622832bea89/session.v4.jsonl.zstd`
  - `dsh/session-456f2d53` Turn 12：同一条要求｜raw: `/home/baowending.bwd/.dsh/sessions/--home-baowending.bwd-RTP-LLM-github-opensource--/session-456f2d53-cae2-4086-94ee-d14f3ef32b16/session.v4.jsonl.zstd`

## R-CFG-03 从真实配置入口核对默认行为与覆盖语义

- **内容**：按产品约定检查缺省和显式输入分别怎样生效。若配置允许「自动」等特殊值，要等依赖的上下文就绪后解析。功能可用与缺省启用是两个问题，审查默认值变更时要分别确认。
- **为什么**：直接给内部字段赋值会跳过真实的默认值。提早解析依赖运行角色的值，会让后面选定的角色采用错误配置。默认行为改变也会影响原本没有传这个选项的调用方。
- **坏例**：
```python
# 入口约定 -1 表示按角色决定，直接把缺省固化成了关闭。
parser.add_argument("--report-interval", type=int, default=0)
```
- **好例**：
```python
parser.add_argument("--report-interval", type=int, default=-1)

def resolve_report_interval(raw: int, role: RoleType) -> int:
    if raw < -1:
        raise ValueError(f"report_interval must be >= -1, got {raw}")
    if raw != -1:
        return raw
    return {RoleType.PREFILL: 100, RoleType.DECODE: 1000,
            RoleType.PDFUSION: 1000}[role]
```
- **判定**：用老配置经原入口启动或解析一次，再检查一项能区分覆盖顺序的显式输入。只核对接口实际支持的取值类别。默认启用新行为时，追到最先受影响的消费者，判断现有配置是否还满足前置条件。
- **例外**：必填字段可以拒绝缺省输入。不同入口也可以有不同的缺省契约，例如用户输入支持「自动」，而已归一化的内部格式只接受确定值。
- **证据**：
  - `codex/2026-10-20T22-35-45` Turn 6：「默认是 0，然后看下如果是 -1 且配置 prefill 设置 100 步汇报一次，decode 设置 1000 步……非默认值校验是否大于 0；然后确认有 ut 覆盖」｜raw: `/home/baowending.bwd/.codex/archived_sessions/rollout-2026-10-20T22-35-45-01a159bd-608e-7ad1-817f-2034addcfee1.jsonl`
  - `codex/2026-10-20T22-35-55` Turn 6：同一指令的另一次下达｜raw: `/home/baowending.bwd/.codex/archived_sessions/rollout-2026-10-20T22-35-55-01a159bd-87dc-7c32-b03f-ca01f9a5c38b.jsonl`
  - session `01a15d3e-ab06-7732-ba3b-af0098e8b866`，2026-10-23 11:04:43（Asia/Shanghai），Turn 未核实，行 8139：「还发现一个问题，这个默认值应该是-1而不是0」，附 CLI `default=0` 与帮助文案。此要求更新了此前默认 0 的项目选择；不否定显式 0 关闭与角色解析契约。｜raw: `/home/baowending.bwd/.codex/sessions/2026/10/22/rollout-2026-10-22T17-19-12-01a15d3e-ab06-7732-ba3b-af0098e8b866_01a162e8-4734-7e01-810d-2803cb609841.jsonl`
  - `remote106/codex/2026-09-24T16-39-17` Turn 4（经 agent 转述）：「删除 block_tree_cache_enable_crc，我们这个应该是默认启用的，除非编译选项不支持（ppu amd 等）；这些应该是代码里的逻辑，不需要参数控制」｜raw: `11.161.48.106:/home/baowending.bwd/.codex/sessions/2026/09/24/rollout-2026-09-24T16-39-17-01a0d291-ab4f-73c2-b236-23711946da6f.jsonl`

## R-CFG-05 容量不足时返回与实际处理范围一致的结果

- **内容**：有容量上限的操作应按对调用方的承诺处理超限输入。承诺处理完整请求时，可以安全扩容、分批完成，或返回失败。如果允许部分处理，调用方必须能从协议中识别已完成的范围。
- **为什么**：完整性校验只检查了前半批却返回整批通过，会让漏掉的数据被当成已经校验。盲目扩容也可能使其他组件持有的地址失效。
- **坏例**：
```cpp
size_t n = std::min(segments.size(), max_segments_);
for (size_t i = 0; i < n; ++i) process(segments[i]);
return Status::OK;  // 调用方以为整批已处理
```
- **好例**：
```cpp
// 本例承诺整批校验，缓冲地址固定。在任何写入发生前拒绝超限输入。
RTP_LLM_CHECK_WITH_INFO(segments.size() <= max_segments_,
    "segments=%zu exceeds preallocated capacity=%zu; split the batch or raise the limit",
    segments.size(), max_segments_);
for (auto& s : segments) process(s);
```
- **判定**：给出比容量多一项的输入，追踪最后一项、已发生的副作用和调用方看到的返回值。如果允许续传或重试，再看调用方能否准确找到继续的位置。
- **证据**：
  - `remote106/codex/2026-10-13T09-19-39` Turn 3（经 agent 转述）：「batch.size() >= 16 && 最大的单个 payload > 16 KiB……之前开的 buffer 放不下怎么办？」——答复为构造期按上限分配、超容拒绝执行｜raw: `11.161.48.106:/home/baowending.bwd/.codex/sessions/2026/10/13/rollout-2026-10-13T09-19-39-01a132d8-0058-7961-9b69-cd0ffdf4fb2d.jsonl`
