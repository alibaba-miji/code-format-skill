# 10 · review 输出契约（R-REV）

> 适用：agent 被要求「review 代码 / 审查 diff / 判断改动是否合理」时。写代码时不需要加载本文件。
> 本文件只约束**报告形态与证据标准**；多模型审查由 `agent-review` 编排。`code-review` 若已安装，可按任务需要参考其方法；缺失不阻塞审查。当前用户要求优先于历史案例的范围与格式。

## R-REV-01 先交代会影响决策的结论

- **内容**：给出审查发现或明确的无发现结论。先写最影响读者决策的结果，再写证据和重要限制。篇幅和顺序以本次委托为准。
- **为什么**：读者通常要先判断是否需要改代码，再追具体证据。只有工具调用或调查经过，读者仍然拿不到结论。
- **坏例**：
```text
我先梳理了本次 delta 的改动范围，接下来准备分三步核对：
第一步看 ExpertLoadMonitor 的窗口推进，第二步看 gather 失败路径……
（读到第 40 行仍没有出现结论）
```
- **好例**：
```text
结论：无可行动问题（范围：8fe6e06..e81cedf，4 个文件）。
已核对：beginStep 是唯一清零点（ExpertLoadMonitor.cc:211 `zero_()`）；
finish 路径为 +=；窗口归约用 int64。
边界：未在 GPU 上跑 graph replay，需单测实证。
```
- **判定**：读者能否找到本次审查的结论和最重要的问题，证据是否足以解释判断。
- **例外**：用户明确要求「先给调查过程」或要求逐文件 walkthrough 时。
- **证据**：
  - `claude/1db811a6` Turn 1：「请直接给最终实质 finding 或"无可行动问题"，最多 300 字，不写计划、不讨论风格、不展开全 feature。」｜raw: `/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/1db811a6-82e5-4efc-be74-3c57eb0ac9ac.jsonl`
  - `claude/bbb141fb` Turn 1：「Maximum 12 final lines. Do not produce a plan or ask for tools.」｜raw: `/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/bbb141fb-d1cf-4129-99a9-05483c8ecaa2.jsonl`
  - `claude/8b20c168` Turn 5：「Produce the final review now from the evidence already inspected.」｜raw: `/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/8b20c168-ca84-40f1-a514-c1504b513d78.jsonl`

## R-REV-02 让每条发现能定位、能复核、能处理

- **内容**：指出被审版本中的问题位置，说明哪种受支持的输入或执行顺序会触发它，以及谁会受到什么影响。有明确的小范围修复时给出建议，仍需设计取舍时写清待解决的行为。多条发现按影响排序。
- **为什么**：能重走触发路径，读者就能核实问题。具体影响决定优先级，修复目标让作者能判断其他解法是否同样有效。
- **坏例**：
```text
- 这里的同步可能有点问题，建议加强一下保护。
- wave 路径看起来没被测试覆盖，建议补测试。
- 变量名 a 不够表意。
（无行号、无触发、无修复）
```
- **好例**：
```text
[P2] <file>:<line>（位置应能在被审版本回查；此处为格式占位）
触发：scatter 后、cudaStreamSynchronize 前抛异常，failures 为空。
影响：整批被标 COPY_FAILED，而 loader 只对 CRC_MISMATCH 失效 source，
      坏 record 会反复失败（调用链 file:line 见下）。
最小修复：catch 中 best-effort 回读 host_failed 并填入 failures。
状态：已证明（调用链）／推断（GPU 未复现）。
```
> 引用历史审查意见时，用本次目标版本核对位置。
- **判定**：读者能否按定位重走因果链，并判断修复是否恢复了预期行为。
- **例外**：文档、生成物或运行时问题可以用段落、符号、事件记录等稳定位置定位。
- **证据**：
  - `claude/3b6d5bee` Turn 1：「Give file:line, trigger, impact and minimal fix; if none remain, say so.」｜raw: `/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/3b6d5bee-d915-4272-8a6d-0177b1b28a2f.jsonl`
  - `claude/768da179` Turn 1：「每项必须包含文件与准确行号、触发条件、实际影响、建议最小修复；区分确认事实与推断。」｜raw: `/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/768da179-16ea-47ef-9d5e-ea49bd957b8f.jsonl`
  - `dsh/session-80c02600` Turn 1（经 agent 转述）：「每条：真实/不真实/部分真实；file:line 证据；建议改法（最小 diff）；风险。」

## R-REV-03 无发现要明说并交代审查边界

- **内容**：没有发现可行动的问题时，说明审查范围。若缺少某类证据会改变读者的判断，指出实际核对到哪一步、剩下哪项行为有待验证。
- **为什么**：「没找到」和「没看」在文本上无法区分；不写边界，结论就无法被信任，也无法判断下一轮该补什么。
- **坏例**：
```text
看完了，没发现问题，可以合入。
```
- **好例**：
```text
无可行动问题。
已核对：step 边界清零、各 writer 均为累加、窗口 int64 归约、无遗留 zero 写入
（ExpertLoadMonitor.cc:211/217）。
未核对：deep_gemm 的 Python wrapper 不在仓库内，dtype 兼容性只按 patch 推断；
日志被截断，capture 期计数残留未实测。
```
- **判定**：读者能否判断哪些路径和结论已有依据，哪些重要行为仍缺证据。
- **证据**：
  - `claude/0fd40310` Turn 1：「没有问题请直接输出"无可行动问题"并简述关键核对。」｜raw: `/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/0fd40310-231c-43d2-a9bd-b664b33394d5.jsonl`
  - `claude/8b20c168` Turn 1：「If no material finding, state the checked scope and limitations concisely.」｜raw: `/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/8b20c168-ca84-40f1-a514-c1504b513d78.jsonl`
  - `claude/0166f8dd` Turn 3：「If evidence is insufficient for a contract, explicitly identify that limitation; reaching a conclusion is not a reason to label the change safe.」｜raw: `/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/0166f8dd-7f09-48e0-9294-a96f5eb83d4c.jsonl`

## R-REV-04 区分本次引入、既有问题与需求本身

- **内容**：比较需求、基线和本次改动，区分新回归、既有行为与预期变化。如果旧缺陷因本次改动而可达或影响扩大，应写清新增的触发条件或影响。
- **为什么**：把历史债务算到本次 PR 上会让作者无从修起；把需求语义报成 bug 会直接毁掉 review 可信度；反过来把新回归说成既有问题则是漏报。
- **坏例**：
```text
发现 bug：step buffer 用 int32 累加，token 多时会溢出。
P1 dump writer 持锁做文件 IO，会拖住传输 worker。
（前者是需求明确要求的语义；后者 base 已存在，均未标注）
```
- **好例**：
```text
非 bug（需求语义）：int32 单步累加、窗口 int64 是 Turn 1 的明确要求；
  溢出仅在单步 token 数 > 2^31 时成立。
既有问题：CrcDumpWriter.cc:127 锁内 IO，base b32c54f 同构，记 follow-up。
本次引入：无。
```
- **判定**：声称问题原来就存在时，是否比较了相关路径在两个版本中的可达性和影响。判为预期变化时，能否指出相应契约。
- **证据**：
  - `claude/8b20c168` Turn 1：「distinguish pre-existing issues and intentional requested semantics.」｜raw: `/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/8b20c168-ca84-40f1-a514-c1504b513d78.jsonl`
  - `claude/7a1afbe8` Turn 4：「Separate inherited behavior and intended per-step int32 accumulation semantics from regressions.」｜raw: `/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/7a1afbe8-3f53-48da-84b0-c5aacac0dba4.jsonl`
  - `claude/a8ab1566` Turn 1：「V4 完整 PD smoke 的 5 项 golden 差异关闭 EPLB 也复现，不要把这些已隔离的差异误当本次新增 bug。」｜raw: `/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/a8ab1566-478b-477f-b7a0-b1a3f858d32f.jsonl`

## R-REV-05 区分已证明与推断

- **内容**：把问题的影响与证据强度分开说明。源码能证明的因果链、实际观测到的结果、仍依赖某个假设的推论，分别给出相应的依据。遇到后果严重但前提未核实的问题，标出该前提和验证方法。
- **为什么**：后果决定排查优先级，证据决定结论能说到哪一步。混在一起会把猜测当事实，也容易漏掉值得优先验证的高影响问题。
- **坏例**：
```text
P1 store 的 mapped 快路径在生产一定失效：torch pinned 不支持
cudaHostGetDevicePointer，所以只拷 payload 的优化等于没做。
（无实测，结论用了「一定」）
```
- **好例**：
```text
## 已证明
CrcBlockCopy.cu:<line> 越界：capacity=9,len=9 时 ASan 报 heap-buffer-overflow（附 ASan 日志路径）。
## 推断（未验证）
torch pinned 在目标机 UVA 下是否返回有效 device alias；若失败则走 fallback，
功能正确但 store 重叠消失。置信度：中。
## 无法验证
需真实 rearrange 的 A/B 性能，本轮无设备。
```
- **判定**：每个关键前提能否落到契约、代码或观测记录。仍有不确定性时，读者能否判断缺什么证据，以及它会如何改变结论。
- **证据**：
  - `claude/8c9ebbc5` Turn 3：「Preserve uncertainty where source did not establish a claim; do not turn an unverified hypothetical into a finding.」｜raw: `/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/8c9ebbc5-dd4f-48f2-bee7-b33e0281e37d.jsonl`
  - `claude/a8ab1566` Turn 1：「明确区分已证明问题和推断。」｜raw: `/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/a8ab1566-478b-477f-b7a0-b1a3f858d32f.jsonl`
  - `dsh/session-2464edb2` Turn 1（经 agent 转述）：「# What I could not verify」

## R-REV-06 将证据对应到本次审查的版本和范围

- **内容**：先确认被审对象是提交、分支差异还是本地未提交改动。查看调用方、依赖和测试时，使用能代表该对象的版本。是否运行验证、是否编辑代码，以本次任务的范围和授权为准。
- **为什么**：把工作区里的临时修复当成 PR 的代码，会漏报尚未修复的问题。反过来，只读已提交对象也看不到用户指定的本地修改。
- **坏例**：
```text
委托审查 EPLB 的两个固定提交，实际却从本地工作区打开 ExpertLoadMonitor.cc。
报告用工作区行号说明清零点已修复，目标提交仍含旧实现。
```
- **好例**：
```text
对 8fe6e06..e81cedf 的 EPLB 变更，按这两个提交比对 diff，
再从 e81cedf 读取 ExpertLoadMonitor.cc 和调用方，核实清零点。
若委托对象改为未提交 diff，则以当前工作区的内容核对同一条路径。
```
- **判定**：证据与结论能否定位到同一份代码。引用其他版本或环境时，是否说清其比较用途。
- **证据**：
  - `claude/8b20c168` Turn 1：「Use only git diff …, git show …:path and git grep at that fixed SHA. Do not read mutable HEAD/working-tree source.」｜raw: `/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/8b20c168-ca84-40f1-a514-c1504b513d78.jsonl`
  - `claude/5f2c5a74` Turn 1：「Do not modify any files, tests, source, git state, checkout, or config. Do not invoke other models.」｜raw: `/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/5f2c5a74-edd4-4a24-a8af-a193f5129dcd.jsonl`
  - `claude/1cd7073f` Turn 1：「All source evidence MUST come from immutable objects.」｜raw: `/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/1cd7073f-23de-446e-a00d-54701ac4dc28.jsonl`

## R-REV-07 把评审意见落到实际契约或维护后果

- **内容**：报告受支持的输入、路径或使用者实际会遇到的问题。结构或可读性问题也应指出具体后果，例如重复条件掩盖可达路径、接口使调用者容易传错参数。未来可能追加的能力、个人风格选择按任务范围处理。
- **为什么**：review 预算有限，噪音会让 P1 失去权重；且「建议加校验」这类泛化建议无法执行、无法验收。
- **坏例**：
```text
- 建议把变量名 a 改成 expert_count。
- 建议给所有入口都加 defined()/numel() 校验。
- 未来支持 ROCm 时这里可能要改。
- 建议把 monitor 重构成插件架构。
```
- **好例**：
```text
本轮 diff 未发现可行动问题。
已核对：窗口推进、warmup 跳过、gather 失败路径。
未覆盖：ROCm 后端（未实测）、EP4 以上真实拓扑（无卡）。
```
- **判定**：能否指出受影响者、受损契约或实际维护成本。调查高影响风险时，哪些条件已得到证实，哪些仍需排除。
- **证据**：
  - `claude/da5780f8` Turn 1：「Avoid style suggestions, hypothetical defensive guards, and expanding old planner functionality.」｜raw: `/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/da5780f8-d4c1-4cc8-90e2-2afa4fd9afc2.jsonl`
  - `claude/768da179` Turn 5：「不要为凑问题扩大到旧代码或理论风险。」｜raw: `/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/768da179-16ea-47ef-9d5e-ea49bd957b8f.jsonl`
  - `claude/bbb141fb` Turn 1：「No style nits, speculative generic defense, future unimplemented policy features.」｜raw: `/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/bbb141fb-d1cf-4129-99a9-05483c8ecaa2.jsonl`

## R-REV-08 引用前回读，独立下结论

- **内容**：复用旧审查、工具或其他 reviewer 的意见前，在当前被审对象上独立检查定位、前提和影响。若代码或需求已经变化，说明原判断在哪个环节失效。
- **为什么**：行号会随 rebase/编辑漂移，旧结论会被后续提交推翻；背书式结论等于没有 review。
- **坏例**：
```text
沿用上一轮结论：CrcBlockCopy.cu:538-539 抛 payload too large（行号未在当前 SHA 回查）。
上一轮 Claude 的结论是没有 material regression，我核对后同意，可以合入。
```
- **好例**：
```text
旧断言「checkGraphInputStable 比较的是 runner 级 buffer」：已过期（HEAD 已是逐实例）。
证据：cuda_graph_runner.cc:1161 传入 graph_instances_[idx].mem_hold_.py_model_inputs_，
       比较对象是当前 graph instance 的持有输入。
上一轮是另一个 reviewer 的意见，不作为证据；我按当前 HEAD 独立复核（下列行号按本次被审快照核对）：
ExpertLoadMonitor.cc:211 是唯一清零点（`zero_()` 一处），无第二个覆盖写，故结论一致。
```
- **判定**：现有证据能否独立支持该结论，旧意见引用的位置与条件是否仍成立。
- **例外**：用户明确要求「只汇总已有结论、不重新审查」时。
- **证据**：
  - `claude/8b20c168` Turn 6：「its answer in this history is another reviewer's opinion, not proof and not a substitute for your conclusion.」｜raw: `/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/8b20c168-ca84-40f1-a514-c1504b513d78.jsonl`
  - `claude/9093e0fd` Turn 5：「This asks for your independent conclusion, not agreement with the implementation.」｜raw: `/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/9093e0fd-0ac0-4ed2-8fa9-d3a405d2cd0d.jsonl`
  - `dsh/session-d8f77613` Turn 1（经 agent 转述）：「必须回到 HEAD 代码核实，引用行号前先 read 确认。」

## R-REV-09 review 必须产出可见结论（已退役）

- **状态**：retired（并入 R-REV-01「结论先行」；「结论必须可见、证据足够即收敛」已写入该卡内容与判定）。
- **证据**：
  - `claude/8dad743d` Turn 7：「不再调用任何工具，不再读更多文件……要提供最终可见答复」｜raw: `/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/8dad743d-7842-4885-b5fa-f1f9d9e37876.jsonl`

## R-REV-10 汇总独立审查时复核分歧和缺失结果

- **内容**：采用多路审查时，由汇总者针对同一版代码核实各条意见，合并重复项，解释影响最终结论的分歧。已修复的旧意见要核对修复结果，缺失或中断的审查要标明状态。
- **为什么**：重复意见可能来自同一个错误前提。某一路中断而没有交付结论，也会让汇总者误以为它已检查过对应风险。
- **坏例**：
```text
沿用上一轮已修复的 finding。某一路达到工具调用上限而中断，汇总时仍将它计为通过。
```
- **好例**：
```text
5 路独立 review → 主 agent 裁决表：
| # | Finding | 裁决 | 依据 |
| F1 | scatter 破坏既有断言 | FIXED | 同一提交已改写三处断言 + 头文件契约 |
| F3 | payload 上限 | 夸大 P2→P3 | 基线同样 OOM，配置不可达 |
| F5 | 缺 wave 计数断言 | 仍成立 | 新增 lastWaveCount() 测试 hook 后复验 |
中断记录：lane3 首次达到工具上限，按未完成处理。续审交付结果后再核实其发现。
```
- **判定**：结论能否追到被审代码或验证结果，分歧是否得到裁决，缺结果的部分是否被误记为通过。
- **证据**：
  - `dsh/session-bea70aa0` Turn 2：「review 当前 crc 性能优化的代码……开多个 subagent 并行独立 review，主 agent 判断并汇总建议。」｜raw: `/home/baowending.bwd/.dsh/sessions/--home-baowending.bwd-new-RTP-LLM-github-opensource--/session-bea70aa0-5d53-47ad-b86a-d1dfa50a17b7/session.v4.jsonl.zstd`
  - `codex/2026-10-20T18-16-51` Turn 1：「使用多个 subagent 并行运行，并且改完以后共同 review，直到没有问题。」｜raw: `/home/baowending.bwd/.codex/archived_sessions/rollout-2026-10-20T18-16-51-01a158d0-5910-78d0-b1c1-0b07300993e8.jsonl`
  - `claude/da5780f8` Turn 3：「Treat that normal-destructor GIL issue as fixed… do not repeat already-fixed findings.」｜raw: `/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/da5780f8-d4c1-4cc8-90e2-2afa4fd9afc2.jsonl`
  - `codex/01a15d3e-ab06-7732-ba3b-af0098e8b866` 2026-10-23 10:16:16（Asia/Shanghai），Turn 未核实，行 7440：「调用超时，研究一下怎么规避，如果glm在正常响应的话，应该是决定等他的」｜raw: `/home/baowending.bwd/.codex/sessions/2026/10/22/rollout-2026-10-22T17-19-12-01a15d3e-ab06-7732-ba3b-af0098e8b866_01a162e8-4734-7e01-810d-2803cb609841.jsonl`

## R-REV-11 区分推导值、观测值与性能预测

- **内容**：给出影响审查判断的数字时，交代它代表什么。推导值给定义、输入与单位，实测结果给测量口径和适用条件。预测有多大收益时，标明依赖哪些假设。
- **为什么**：同一个数字可能是理论上限、单次样本或一组观察的统计量。省略口径会让读者误用它作决策。
- **坏例**：
```text
- 每条 encoded 是 510,928B。
- 降阈值能提升 BS=8 的 H2D 性能。
- 本 PR 性能提升约 20%。
（无公式、无对照、无样本量；另附一张无纵轴单位的趋势图）
```
- **好例**：
```text
encodedBytes(P) = (P + 4 + 15) & ~15
P = 510,912 → 510,928（padding 12B + footer 4B）
BS=8 实测（独占 B300、锁卡、预热后 600 采样，paired median）：
| 实现 | P50 (ms) | 基线 P50 (ms) | 降幅 |
| 本实现 | 0.147 | 0.186 | 21% |
本次对照采用相同 ckpt 和采样配置，并记录了测量顺序。
```
- **判定**：能否复算推导值，能否解释实测值的单位、范围和来源。声称实际提升时，证据是否覆盖该场景。
- **证据**：
  - `dsh/session-0b8eb0fa` Turn 27：「full 每条 encoded 510,928B 是咋算出来的？」；Turn 29：「如果降低阈值，是否能够降低 bs=8 时候的 crc 延迟？」｜raw: `/home/baowending.bwd/.dsh/sessions/--home-baowending.bwd-new-RTP-LLM-github-opensource--/session-0b8eb0fa-7da5-4386-bb5e-00562a9c331d/session.v4.jsonl.zstd`
  - `codex/2026-10-19T10-42-15` Turn 1：「性能确认用 bbdetector 找一台空闲的 b300 机器，并且用 nvidia-smi 锁卡避免性能测试不准，测完放开。」｜raw: `/home/baowending.bwd/.codex/archived_sessions/rollout-2026-10-19T10-42-15-01a15209-ca85-7781-8d50-c741fbfff905.jsonl`
  - `codex/2026-10-19T15-19-20` Turn 1：「用绿色+加粗表示性能最好的实现」；Turn 2：「并且 pr 里的趋势图删了，那个不直观。」｜raw: `/home/baowending.bwd/.codex/sessions/2026/10/19/rollout-2026-10-19T15-19-20-01a15307-75a1-73f0-bf6a-038e5f8af2e6.jsonl`

## R-REV-12 对照实验要能区分改动效果与环境差异

- **内容**：比较两个实现时，先界定观测对象和统计口径，再检查负载、配置、测量边界及环境中会影响结论的差异。可以控制这些因素，也可以用分组、配对或额外对照来估计其影响。
- **为什么**：对照组多做一次拷贝，或两个版本面对不同负载，都能产生看似属于代码的差值。历史案例把跨时段、跨基准工具测得的 16% 差异归给了 CRC 实现。
- **坏例**：
```text
before：02:09 夜间，.113 GPU5，旧 harness（4 variants）
after ：12:28 中午，.113 GPU5，新 harness（5 variants）
结论  ：CRC 路径 +16% → 判定为代码回退

| variant | speedup vs main |
| CRC     |           3.2x  |   ← 无绝对耗时，BS 点自选
```
- **好例**：
```text
同构对照：同一 staging、同一 HOST 地址、同一 kernel，只摘掉 CRC
crc   = runCrcPath(crc_enabled=true)
nocrc = runCrcPath(crc_enabled=false)

| BS | staged p50 (µs) | CRC p50 (µs) | 差 |
|---:|---:|---:|---:|
|  1 | 182.4 | 190.1 | +7.7 |
| 32 | 3465.5 | 3505.1 | +39.6 |
footer: SHA a8cbe86e / .113 GPU5 L20D / seed 20261004 / warmup 30 + 100 samples / paired median
```
- **判定**：基线能否回答本次对比的问题。差值与环境波动、取样偏差或其他改动之间是否还有无法区分的解释。
- **例外**：可比性有限的数据可以作为排查线索，结论要写明能比较到哪一步。
- **证据**：
  - `remote106/codex/2026-10-12T22-24-05` Turn 24：「性能测试的不对啊，为啥优化 staged 性能不如 crc？crc 应该就是优化 staged 路径 + crc 计算逻辑，应该是严格不如优化 staged 的」｜raw: `11.161.48.106:/home/baowending.bwd/.codex/sessions/2026/10/12/rollout-2026-10-12T22-24-05-01a12fdf-184f-7a90-9d06-d076dd59a89a_01a1307f-d112-70d1-a65b-a4dbc465c319.jsonl`
  - `remote106/codex/2026-10-12T22-24-05` Turn 13：「表格列的不好，要绝对时间，不要对比，然后列出 1-4-8-16-24-32bs 的时间」｜raw: `11.161.48.106:/home/baowending.bwd/.codex/sessions/2026/10/12/rollout-2026-10-12T22-24-05-01a12fdf-184f-7a90-9d06-d076dd59a89a_01a1307f-d112-70d1-a65b-a4dbc465c319.jsonl`
  - `remote106/claude/a3313e18` Turn 46：「分别从 d2h 和 h2d 场景，告诉我你对比基线优化了什么；为啥 bs32 还能比非 crc 快」｜raw: `11.161.48.106:/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/a3313e18-6c93-4776-baf2-f43dd88f53e7.jsonl`

  - `remote106/codex/2026-10-12T22-24-05` Turn 13：「表格列的不好，要绝对时间，不要对比」＋同批「一个 flag 不许同时改两个维度；warmup 须各变体对齐自己消费的输入」｜raw: `11.161.48.106:/home/baowending.bwd/.codex/sessions/2026/10/12/rollout-2026-10-12T22-24-05-01a12fdf-184f-7a90-9d06-d076dd59a89a_01a1307f-d112-70d1-a65b-a4dbc465c319.jsonl`
  - `remote106/codex/2026-10-13T10-19-40` Turn 5（经 agent 转述）：「确认存在对照路径未对齐」；Turn 1：「表格里每一列最好和最坏用不同颜色标出来」；Turn 8：「每次 staged 调用强制核对 memcpy_calls == BS」｜raw: `11.161.48.106:/home/baowending.bwd/.codex/sessions/2026/10/13/rollout-2026-10-13T10-19-40-01a1330e-f287-7de2-a077-a99aaa5b6019.jsonl`

## R-REV-13 性能归因要有能区分成因的证据

- **内容**：报告“慢了多少”时记录足以解释结果的代码版本、负载和测量条件。进一步声称“慢在哪里”时，选择能区分候选原因的证据，例如阶段计时、请求追踪、剖析或控制变量对照。
- **为什么**：端到端耗时包含计算、调度与等待。差值能说明整体变化，单凭差值无法判断哪一段造成它。
- **坏例**：
```text
gather→CRC→D2H 620.7µs，gather→D2H 545.2µs
⇒ 结论："CRC 计算开销 75.5µs，无法避免"     # 其中可能含 status D2H 造成的空闲

"copy 速度不应该有这么大的 diff" → 回答"GPU 上就是有波动，多跑几次取中位数即可"
（报告只有 p50，没有 p95/max/长尾计数，也没写两侧跑在哪张卡）
```
- **好例**：
```text
| 相位                    | staged_no_crc | crc      | 差    |
| payload H2D（DMA）      | 21.3 µs       | 22.5 µs  | +1.2  |
| CRC 计算 kernel         | —             | 17.7 µs  | +17.7 |
| finishCrc（判决）       | —             | 3.9 µs   | +3.9  |
| scatter（launchCopyTiles）| 3.9 µs      | 3.7 µs   | ≈0    |
| launch API + DMA 空隙   | ~21 µs        | ~24 µs   | +2.4  |
这里直接测得 CRC kernel 用时 17.7 µs。其余阶段也有差值，不能把端到端差值全部计为 CRC 计算。
（kernel 名以当前 CrcBlockCopy.cu 为准；历史会话中的自研 kernel 名仅作示意。）

| 指标 | 旧数据 | 重放 |
| p50 | ~250 µs | ~249 µs |
| p95 | 672.6 µs | 252.6 µs |
| max | 68.6 ms | 257.2 µs |
115,200 样本，同一 source_plan；差异已定位到 host 侧 CPU pack / API 提交。
```
- **判定**：观测结果能否支持所声称的归因。若讨论长尾，样本和统计方式能否观察到尾部。记录能否定位到被测代码与环境。
- **例外**：只验证端到端目标时，用与目标一致的指标即可。多种解释仍成立时，保留已观测的差值，标明归因待定。
- **证据**：
  - `remote106/codex/2026-09-22T17-43-15` Turn 40：「你先 profile 一下……如果是状态 D2H 带来的空洞话，那就要设计方案解决」｜raw: `11.161.48.106:/home/baowending.bwd/.codex/sessions/2026/09/22/rollout-2026-09-22T17-43-15-01a0c848-ffe1-7550-bfe4-caeab54c1775_01a0c87f-8474-7a42-afed-5a402d03d8b0.jsonl`
  - `remote106/codex/2026-10-02T17-54-17` Turn 2：「copy 速度不应该有这么大的 diff，应该是个稳定的情况，你看下为什么」｜raw: `11.161.48.106:/home/baowending.bwd/.codex/sessions/2026/10/02/rollout-2026-10-02T17-54-17-01a0c848-ffe1-7550-bfe4-caeab54c1775_01a0fc09-37be-7f22-985b-db7fced9962a.jsonl`
  - `remote106/claude/a8b41b73` Turn 4：「测试性能时候要用 sudo nvidia-smi -i 0 -c EXCLUSIVE_PROCESS 锁卡，测试完用 … DEFAULT 恢复……待测代码先提交，保证记录的 SHA 对应实际源码」｜raw: `11.161.48.106:/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/a8b41b73-5ac1-45e3-89d9-c033025995d3.jsonl`

## R-REV-14 检查并发操作在完成、失败和退出时的顺序

- **内容**：当改动涉及并发读写、等待或后台回调时，沿调用链核对同步顺序和资源生命周期。出现失败或取消时，追到等待方如何获知结果、共享对象由谁释放。若这条路径还会触发重试或回退，核对其触发条件与原约定。
- **为什么**：成功路径中的完成通知不能证明失败路径也会唤醒等待者。回调与析构顺序失配，可能产生悬空访问或在退出时卡住。
- **坏例**：
```text
审查结论：逻辑正确，测试通过，可合入。
（没有说明锁内是否阻塞、失败时是否改动既有回退、多流下是否有竞态）
```
- **好例**：
```text
并发：
- 锁内只做状态选择（select/摘链），阻塞 IO 与 GPU 等待都在锁外；
- 回调持有 shared_ptr 快照，节点析构后不会解引用；
- 多流：copy_stream 与 compute stream 之间有 event 依赖，未发现裸露读写。
回退：
- 新增失败路径不改变既有 fallback 判定（仍按 status 丢弃，不删健康 block）；
- 逐项核对：I/O 失败不再升级为「数据污染」。
```
- **判定**：能否给出一条可达的交错顺序，说明哪一步同步或生命周期约束使它安全。出错、取消和调用方离开时，未完成操作是否得到约定的处置。
- **真实案例**：服务初始化放在后台线程时，异常可能逃出线程入口，调用方却还在等 ready。将初始化移到调用线程后，还要追服务是否继续借用旧线程的栈参数。
- **坏例（启动异常没有返回通道）**：
```cpp
std::thread([this] {
    initializePythonRuntime();  // 可抛 Python/C++ 异常
    ready = true;
}).detach();
while (!ready) { sleep(1); }
```
- **好例（同步初始化并明确持有需要的配置）**：
```cpp
// 后台 RPC 工作由服务自身管理；初始化异常直接返回调用方。
auto service = std::make_unique<Service>();
service->initialize(params);
http = std::make_unique<HttpApi>(params.model_config); // 按值持有所需配置
rpc = std::move(service);
```
- **证据**：
  - `remote106/codex/2026-10-14T15-35-08` Turn 1（经 agent 转述）：「开 3 个 subagent 分别独立 review……从代码逻辑/代码风格/没有过度防御/没有给潜在回退/多线程 copy 时候没有锁竞态几个角度 review 代码」｜raw: `11.161.48.106:/home/baowending.bwd/.codex/sessions/2026/10/14/rollout-2026-10-14T15-35-08-01a13956-2113-73d0-8782-514146b1cae1.jsonl`
  - `remote106/codex/2026-10-08T15-14-50` Turn 1（经 agent 转述）：「多线程 copy 时候没有锁竞态」（archived 会话，同一句）｜raw: `11.161.48.106:/home/baowending.bwd/.codex/archived_sessions/rollout-2026-10-08T15-14-50-01a11a5d-6360-7521-b798-48271942edd9.jsonl`
  - `remote106/codex/2026-09-24T17-55-03` Turn 1（经 agent 转述）：「kernel 统一成一个，用一个 block 用多少个 thread，按照 deepseek v4 + seq_size_per_block 128 测试来 profile 哪个性能更好」｜raw: `11.161.48.106:/home/baowending.bwd/.codex/sessions/2026/09/24/rollout-2026-09-24T17-55-03-01a0d2d7-0a88-7753-98cc-1c21068369ef.jsonl`
  - session `01a16309-49be-7181-970b-abfa99b86c2f`，2026-10-23，Turn 未核实：「grpc_server_thread_ 又是 detach 的，异常逸出直接 std::terminate，Python 侧还在 while (!is_server_ready_) 等」。本轮源码确认初始化异常逸出；修复时另发现 HttpApiServer 借用该线程栈参数。｜raw: `/home/baowending.bwd/eplb-work/01a16309-49be-7181-970b-abfa99b86c2f/verify-only/v41/source-excerpts.txt`

## R-REV-15 迁移职责时同时核对旧入口、新入口和下游消费点

- **内容**：操作换了组件、进程或执行阶段时，从基线定位谁触发它，再在改版中分别追旧调用方和新调用方。沿同一业务输入对照前后的执行次数、顺序、结果交给谁，以及失败如何到达调用方。
- **为什么**：新入口走通时，旧入口仍可能重复执行；另一个调用方也可能漏做原来的操作。例如把扣款从控制器移到订单服务，两边都扣会重复收费，遗漏入口则可能生成未付款的订单。
- **坏例**：
```text
示意审查记录
新增 prepare_host()，里面可以看到 TCPStore 注册，所以建联迁移完成。
```
- **好例**：
```text
PR #1790 的代码对照（3ac0b937eb → fe36baa064）
基线：BackendManager 构造 DistributedServer，并在 start 中触发原注册流程。
改版旧入口：BackendManager 读取 WorkerTopology，后端仍使用最终通信地址。
改版新入口：多机每个 launcher 登记一次主机地址，启动 Store 在 rendezvous 结束时释放。
关闭筛选仍用原拓扑；开启时只有被剔除机离开原服务入口。
```
- **判定**：① 从受影响的真实入口比对基线与改版，定位旧调用在新版本中被移除、转发或保留的位置；有开关时核对两态。② 追到首次消费结果的位置，对照成功路径和可达失败的处理者；涉及资源时也追到释放点。③ 有意保留的兼容入口要说明触发条件和最终执行者，区分正常复用与重复执行。
- **例外**：纯改名或文件搬动且调用者、执行时序和资源所有者均未变时，核对引用更新即可。允许显式双写或灰度并行的迁移，以其约定的执行次数和结果归属为准。
- **证据**：
  - `codex/01a1f28b-91db-7bb0-9891-0bb77fc96ebb`，2026-11-24T09:04:13Z，第 1805 行，Turn 未核实：「我只看到新增了prepare_host流程，但是没看到应该在哪里有删除现有的流程啊」。这条追问要求补上旧入口证据，未指称最终 PR 存在重复注册。｜raw: `/home/baowending.bwd/.codex/sessions/2026/11/24/rollout-2026-11-24T15-55-41-01a1f28b-91db-7bb0-9891-0bb77fc96ebb_01a20c8d-ae7c-7192-9987-926c23140fc4.jsonl`
  - 同一会话，2026-11-24T09:15:49Z，第 2191 行，Turn 未核实：「DistributedServer本身还是有用的吧，只是需要挪位置到backend_server外面」。对照文件为 `rtp_llm/server/backend_manager.py`、`rtp_llm/distribute/host_bootstrap.py` 与 `rtp_llm/distribute/distributed_server.py`。｜raw: `/home/baowending.bwd/.codex/sessions/2026/11/24/rollout-2026-11-24T15-55-41-01a1f28b-91db-7bb0-9891-0bb77fc96ebb_01a20c8d-ae7c-7192-9987-926c23140fc4.jsonl`
