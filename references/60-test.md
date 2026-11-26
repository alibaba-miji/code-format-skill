# 60 · 测试与验证（R-TST）

> 适用：写/改测试，或报告「已验证」时。
> 评审高成本用例时读 R-TST-06 判断它额外覆盖的失败。核对用例是否实际执行、通过数如何计算时读 R-TST-03。

## R-TST-01 测试必须能真实失败，不得削弱 oracle

- **内容**：从测试声称保证的行为出发，检查断言和替身能否观察该行为。判断断言是否被削弱时，指出一种违反契约的实现，在旧断言下失败、在新断言下却会通过。
- **为什么**：如果 mock 截断了被测路径，改错生产实现后用例也可能一直通过。反过来，接口允许任意顺序时，把固定顺序断言换成多重集相等，仍可发现丢项、多项和重复项。
- **坏例**：
```cpp
// 为了让测试过：期望从 3 行改成 1 行；用假数据喂假 collective
EXPECT_EQ(out.size(0), 1);                 // 原断言是 3，被放宽
fake_collective->setCounts({1, 1, 1});     // 真实 NCCL 路径未被执行
```
```python
# patch 整个构造，把被测的 metadata/pool 行为一起盖掉
with patch("rtp_llm.models_py.modules.dsv4.utils._v4_fp8_linear", return_value=None):
    attn = build_everything()
    result = attn.run()          # 断言通过，但没测到东西
```
- **好例**：
```python
# 只隔离不需要的 Q projection；其余 metadata/compressor/pool/gather 走真实实现
with patch("rtp_llm.models_py.modules.dsv4.utils._v4_fp8_linear", return_value=None):
    attn.indexer = IndexerFP8(...)
build_and_gather()               # 真实 builder + 真实 kernel
assert captured == eager         # oracle 与原实现逐字段一致
```
- **判定**：沿测试入口追到被测行为和最终断言。若期望值、跳过条件或 mock 范围发生变化，尝试构造一个本应报错却会通过的输入。重复断言合并后，按剩余断言的实际覆盖判断。
- **例外**：契约改变后按 R-TST-02 更新期望。明确支持的近似结果或多种合法输出，可以按误差界或不变量断言。
- **证据**：
  - `claude/cc50a296` Turn 1：「Find concrete material test regression or weakened oracle, with trigger/location/fix」｜raw: `/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/cc50a296-423a-4157-922a-1e559360365e.jsonl`
  - `claude/a0192d2a` Turn 1：「whether the patched factory is the constructor's actual lookup target, whether its scope masks any operation that this test is meant to validate」｜raw: `/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/a0192d2a-3998-4424-b167-4a38dfb59bde.jsonl`
  - `claude/bbb141fb` Turn 1：「it must call the actual production Python NCCL closure and real collective, not mock data」｜raw: `/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/bbb141fb-d1cf-4129-99a9-05483c8ecaa2.jsonl`

## R-TST-02 契约变化要有能区分新旧行为的断言

- **内容**：先指出调用方能观察到的变化，再检查已有断言能否捕获回退到旧行为的实现。可改已有用例，也可补缺失的边界。如果接口仍接受旧输入，还要核对承诺保留的行为。
- **为什么**：例如计数从覆盖改为累加时，只调用一次会使两种实现得到相同结果。连续两次写入并观察总量，才能捕获这次回归。
- **坏例**：
```python
# 语义从「覆盖写」改成「累加」，只把期望值从 [9] 改成 [9,18]，不新增用例
assert counts.tolist() == [[9], [18]]
```
- **好例**：
```python
def test_multiple_contributions_accumulate_until_next_step():
    # record(tokens_per_expert)：把本 chunk 每个 expert 的计数加到 step buffer
    record([0, 0, 0]); record([1] * 6); record([2] * 5)
    assert counts.tolist() == [3, 6, 5]       # 同一步内跨 chunk 累加
    begin_step()
    assert counts.tolist() == [0, 0, 0]       # 本例的 step 边界清零
```
- **判定**：取能区分新旧行为的一组输入或操作序列，检验断言。契约明确拒绝某类输入时，检查对应错误的断言。验证范围按本轮要求执行。
- **例外**：纯实现调整可复用现有契约测试。测试的默认配置也属于输入，只有会改变目标路径的配置层才需要在夹具中固定。
- **证据**：
  - `codex/2026-10-20T18-15-52` Turn 1：「全部做完以后更新 ut 并跑 smoke，确认都没问题」｜raw: `/home/baowending.bwd/.codex/archived_sessions/rollout-2026-10-20T18-15-52-01a158cf-71f0-7963-a2af-0556227e7c9f.jsonl`
  - `claude/8b20c168` Turn 1：「… and tests that no longer exercise a necessary contract」｜raw: `/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/8b20c168-ca84-40f1-a514-c1504b513d78.jsonl`
  - `codex/2026-10-22T11-21-51` Turn 4：「改完之后只跑 ut，不跑 smoke」｜raw: `/home/baowending.bwd/.codex/sessions/2026/10/22/rollout-2026-10-22T11-21-51-01a161a1-1e0b-7cf0-b8b2-fec51d24b312.jsonl`

## R-TST-03 验证结论必须与实际执行对齐

- **内容**：把验证结论对应到实际运行的版本、输入、路径和断言。分别说明本轮执行、复用的成功结果和未覆盖项。任务被取消、跳过或进程异常退出时，按实际结果报告。
- **为什么**：缓存成功可以覆盖相同输入。若拿它证明新代码在另一套环境实跑过，或只看断言就漏掉退出时的崩溃，读者会据此作出错误判断。
- **坏例**：
```text
「UT 全部通过」        ← 实际 186 个 target 全部命中缓存，本轮执行 0 个
「已跑过 smoke」        ← 实际只改了 Python 字段，smoke 没启动
「审查完成，无问题」    ← 首次 max-turns 中断，续审才跑完
「11/11 断言通过，exit -6 是收尾噪音」  ← 未解释的 abort
「target/draft 都有快照、双卡 UT 通过，所以已确认 commit 不统计」
  ← 快照无 phase；UT 直接给 monitor 喂数，未经过 MtpExecutor 的阶段路由
「PR 连续两次 host OOM，因此已确认外部确定性故障」
  ← 只重跑了新代码；参考基线的同一 target 实际通过
```
- **好例**：
```text
本机 33 项 Python 测试实跑通过；GPU UT / 编译 / 服务 smoke 未执行。
186 个 target 通过，其中本轮实际执行 0 个（全部命中缓存），不能作为重新执行验证。

11/11 断言通过后 exit -6；readelf 显示 librtp_compute_ops.so 与静态测试依赖同时存在
→ 判定为 DSO 重复链接，不算通过；已从 srcs 移除该 DSO。
历史 V4 smoke 证明 target/draft 都产生过非零窗口，但快照无 phase，不能证明 commit 被排除。
双卡 monitor UT 证明独立计数和 NCCL 汇总；阶段过滤需另查调用方及 wrapper 选择。
当前源码核查：DSpARK 的 commit 使用关闭监控的 wrapper；普通 MTP graph 关闭时
commit 回落到启用监控的 draft_model_，因此不能声称所有投机采样 commit 都被排除。
Pro 基线同 target、同 scratch 参数实跑通过；新版本在 CPU 权重转换时被 cgroup 杀死。
监控尚未构造、加载前 RSS 无增长，支持排查加载/环境；未测加载峰值与 pod 占用，归因待定。
```
- **判定**：核对用例选择、最终退出状态和结论声称的覆盖范围。统计数按声明的单位去重。归因到环境或已有问题时，找能区分该解释与代码变更的证据，例如旧版本在相同限额下的对照。多次观察到同一症状，本身不能确定成因。
- **例外**：旧运行或缓存与新结论仍有关时，说明复用依据。例如只改文档且文档不参与构建和测试输入，可以引用原有运行并注明版本。实现、依赖或运行条件的变化影响结论时，重跑受影响部分，或标明尚待验证。
- **证据**：
  - `codex/2026-10-22T11-30-49` Turn 4：「改完之后只跑 ut，不跑 smoke」｜raw: `/home/baowending.bwd/.codex/sessions/2026/10/22/rollout-2026-10-22T11-30-49-01a161a9-52d2-77e3-8565-097763229970.jsonl`
  - `claude/3b6d5bee` Turn 2：「Do not treat those tests as passing or dismiss as unrelated teardown.」｜raw: `/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/3b6d5bee-d915-4272-8a6d-0177b1b28a2f.jsonl`
  - `claude/1cd7073f` Turn 2：「Do not claim any tests were run.」｜raw: `/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/1cd7073f-23de-446e-a00d-54701ac4dc28.jsonl`
  - `codex/01a15d3e-ab06-7732-ba3b-af0098e8b866` 2026-10-22 17:43:56（Asia/Shanghai），Turn 未核实，行 425：「有实际确认过draft和target model都会汇报监控，且commit阶段不汇报，只汇报prefill/ decode target verify / decode draft propose吗」｜raw: `/home/baowending.bwd/.codex/sessions/2026/10/22/rollout-2026-10-22T17-19-12-01a15d3e-ab06-7732-ba3b-af0098e8b866_01a162e8-4734-7e01-810d-2803cb609841.jsonl`
  - `codex/01a15d3e-ab06-7732-ba3b-af0098e8b866` 2026-10-23 10:16:16（Asia/Shanghai），Turn 未核实，行 7440：「有确认过，这个OOM是符合预期的嘛？是否是我们引入的」｜raw: `/home/baowending.bwd/.codex/sessions/2026/10/22/rollout-2026-10-22T17-19-12-01a15d3e-ab06-7732-ba3b-af0098e8b866_01a162e8-4734-7e01-810d-2803cb609841.jsonl`

## R-TST-04 替换实现时按契约验证等价，按性能声明选择对照

- **内容**：用调用方依赖的输出、状态变化或错误行为检验替换是否等价。声称性能改善时，用可比工作负载对照新旧实现，覆盖所声称受益的输入范围。
- **为什么**：校验和相差一位就会破坏兼容。某个吞吐指标在大批量上改善，也可能掩盖小批量请求的退化。两个结论需要不同的证据。
- **坏例**：
```cpp
// 只有"能跑通 + 与历史 p50 差不多"的软验证
ASSERT_EQ(batch.store(items, &failures), CrcCopyStatus::OK);
EXPECT_NEAR(custom_kernel_us, 21.3, 2.0);   // 21.3 来自上一次会话的跑分

// commit: "refactor: move sm_copy_kernel.h helpers into CopyTileKernel.h"
// 未声明：默认线程 512->256、移除手动 block 数、尾部处理方式改变
```
- **好例**：
```cpp
// 同一批 payload，三个独立来源必须给出同一个 32 位值
// 注：以下 oracle 函数名为示意；实现替换后原库依赖可能已移除，需自建独立参考实现
EXPECT_EQ(sealedFooter, crc32cReference(host_payload, len));   // 逐字节软件参考
EXPECT_EQ(sealedFooter, nvcompChecksums[i]);                   // 旧实现作独立 oracle
EXPECT_EQ(sealedFooter, 0xE3069283u);                          // 已知向量
// 这个用例还在选定的长度上翻转 payload 位，核对 load 能发现损坏
```
- **判定**：从契约决定比较方式和判错依据，例如标准向量、独立实现或有依据的数值容差。报告加速时，核对双方工作量、测量边界以及会改变结论的工作负载差异。
- **例外**：只移动代码且未声称性能变化时，按 R-REV-15 检查入口和实际行为。已有测试足以约束此次搬移的行为时可直接复用。
- **证据**：
  - `remote106/claude/a3313e18` Turn 26：「替换 nvCOMP CRC32C 为自定义 crc32cBatchedKernel：需要真实 benchmark 他的收益，以及对 crc32cBatchedKernel 做更严格的测试，确认和原 kernel 精度一致，要有非常详细的 ut」｜raw: `11.161.48.106:/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/a3313e18-6c93-4776-baf2-f43dd88f53e7.jsonl`
  - `remote106/codex/2026-10-09T11-16-12` Turn 1：「删除了 sm_copy_kernel.h 的一堆函数，放到 CopyTileKernel.h 里，他们功能是否等价？」｜raw: `11.161.48.106:/home/baowending.bwd/.codex/sessions/2026/10/09/rollout-2026-10-09T11-16-12-01a11ea9-4492-7742-bbc8-42f36ddbb4e1.jsonl`
  - `remote106/claude/a8b41b73` Turn 26：同一替换要求的另一次下达｜raw: `11.161.48.106:/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/a8b41b73-5ac1-45e3-89d9-c033025995d3.jsonl`

## R-TST-05 可选功能关闭时，验证承诺保留的行为

- **内容**：实现承诺关闭功能后仍兼容旧调用方时，先列出应保持的可观察结果，再检查修改前后对这些结果的证据。新版本内部切换开关，只能说明新代码的两个分支有何差别。
- **为什么**：例如关闭负载均衡时，新旧两条开关路径仍可能共用改错的权重映射。只比较开关两态，会漏掉它们共同引入的问题。
- **坏例**：
```text
smoke 比对：expected(golden) == actual → 5 项 diff
agent 处理：把 golden 更新为新输出，并在 PR 里写「行为符合预期」
```
- **好例**：
```text
对照：同一批用例，旧源码基线、新源码关闭、新源码开启分别保存实际响应；
      三者同样 20/25 匹配历史 golden，23 份响应按约定口径逐值一致。
      用户明确以修改前等价为验收时，历史 golden 的共同失败单列，不冒充新增回归。
迁移：物理专家编号/所在 rank 发生变化；按 logical expert 对齐后比较权重和结果。
      说明原始张量与对齐后的比较范围，不把“逻辑结果相同”说成“所有物理数据相同”。
本例分别核对受变更影响的阶段和运行模式，记录实际进入的实现。
```
- **判定**：从受影响的真实入口选择输入、基线和断言，按契约比较数值、顺序、错误或副作用。若结果已分叉，固定足以复现差异的输入找到最早可观察的分歧。若观测工具改变了执行路径，标明证据能支持的范围。
- **例外**：对外输出允许随机、近似或多种顺序时，按约定的不变量或容差比较。需求明确改变的行为按新契约验证，保留行为仍按原契约验证。
- **证据**：
  - `remote106/codex/2026-10-14T18-49-18` Turn 1（root user 引文，经 agent 转述）：「golden 不一致是不合理的，eplb 不应该改变任何原先的执行结果」「只要确认开关 eplb 能得到一样的结果就行了」｜raw: `11.161.48.106:/home/baowending.bwd/.codex/sessions/2026/10/14/rollout-2026-10-14T18-49-18-01a13a07-e3d9-7ec3-8b6e-ad41a07edfd1.jsonl`
  - `remote106/codex/2026-10-14T16-04-20` Turn 1：「golden 不一致是不合理的，eplb 不应该改变任何原先的执行结果」｜raw: `11.161.48.106:/home/baowending.bwd/.codex/sessions/2026/10/14/rollout-2026-10-14T16-04-20-01a13970-dea6-7391-94dd-b00bbc2d45a4.jsonl`
  - `remote106/claude/2d8f65f8` Turn 11：「统计对象必须是实际执行的 physical expert assignments……」｜raw: `11.161.48.106:/home/baowending.bwd/.claude/projects/-data0-baowending-bwd-new-RTP-LLM-github-opensource/2d8f65f8-3028-4adc-8a2d-5a2aa79d2fe7.jsonl`

  - `codex/01a16309-49be-7181-970b-abfa99b86c2f` 2026-10-22，Turn 未核实：「对于精度误差，你要确认是eplb引入的，还是说是中间结果出问题了」｜本次公开裁决记录：`/home/baowending.bwd/eplb-work/01a16309-49be-7181-970b-abfa99b86c2f/user-precision-feedback.md`（未读取或导出根会话隐藏内容）
  - `codex/01a16309-49be-7181-970b-abfa99b86c2f` 2026-10-23，Turn 未核实：「不对啊，专家自动调度前后，megamoe应该执行的逻辑不一样了？为啥张量还能完全一致；golden不一致倒是不用特别在意，只要和修改前一直就行」｜本次公开裁决记录：`/home/baowending.bwd/eplb-work/01a16309-49be-7181-970b-abfa99b86c2f/user-baseline-feedback.md`（前后版本对照及物理/逻辑口径；历史 golden 的验收取舍限本项目）

## R-TST-06 高成本用例须说明相对现有覆盖能独立发现哪种失败

- **内容**：新增或扩大高成本测试时，给出一个现有较便宜的测试仍会通过、新测试会失败的具体场景，并定位观察该故障的断言。比较最接近的已有集成用例，再决定独立运行、并入它或在较低层验证。
- **为什么**：端到端测试的成本来自实际跨过的边界。支付回调超时后重试是否产生两笔真实扣款，可以是集成测试独有的观察；同一套环境中重复断言金额舍入，则可能只增加运行时间和偶发失败。
- **坏例**：
```text
示意反例
已有 UT 穷举 HTTP 探针路径和方法。
为每个路径另启一套四卡模型，只检查同一个 HTTP 状态码。
```
- **好例**：
```text
PR #1790（fe36baa064）的四卡用例
UT 负责筛选规则和探针矩阵，原有 DeepSeek-V4 smoke 直接启动 2P + 2D。
新 smoke 从四卡 decode 剔除一台，以剩余两卡运行 decode，在被剔除的两卡上启动 prefill。
真实请求断言 finished 和 aux_info.pd_sep，能抓到选机成功后 P/D 交接失败。
```
- **判定**：① 对照实际 fixture、启动参数及断言，确认现有用例能否观察同一失败。② 检查新断言穿过发生故障的边界，确认断言会在所述回归发生时失败。③ 若要求自动回归，从目标 suite 或流水线入口追到 test target，核对运行资源和过滤条件；测试可手工启动或单独带有 `manual` 标签，都不足以判断它是否会被该入口选中。运行结果按 R-TST-03 另行确认。
- **例外**：用户明确要求手工诊断、固定发布门禁或独立长稳测试时，按其用途和成本说明检出能力；不据此增加自动执行要求。廉价单测不必逐个编制 smoke 对照。
- **证据**：
  - `codex/01a1f28b-91db-7bb0-9891-0bb77fc96ebb`，2026-11-25T02:57:05Z，第 5549 行，Turn 未核实：「剩下两张卡的 decode 拓扑正确，再用被剔除的两张卡起 prefill，跑通一条真实请求。」对应 `rtp_llm/test/smoke/dsv4_host_selection_test.py`。｜raw: `/home/baowending.bwd/.codex/sessions/2026/11/24/rollout-2026-11-24T15-55-41-01a1f28b-91db-7bb0-9891-0bb77fc96ebb_01a20c8d-ae7c-7192-9987-926c23140fc4.jsonl`
  - `codex/01a211cd-fdf8-7252-bf92-8f096efabd7f`，2026-11-25T09:54:17Z，第 1373 行，Turn 未核实：「并且他是否集成进了smoke链路，而不是manual的」。`fe36baa064` 的目标显式列在 `suites_cuda13.bzl` 的 `smoke_cuda13_x86` 中。｜raw: `/home/baowending.bwd/.codex/sessions/2026/11/25/rollout-2026-11-25T16-24-02-01a211cd-fdf8-7252-bf92-8f096efabd7f.jsonl`
  - 同一会话，2026-11-26T03:19:38Z，第 2731 行，Turn 未核实：「是不是加的测试过多了，原来的smoke有修改吗」。上面的坏例是区分测试层级的示意，PR 中没有逐探针启动四卡模型。｜raw: `/home/baowending.bwd/.codex/sessions/2026/11/25/rollout-2026-11-25T16-24-02-01a211cd-fdf8-7252-bf92-8f096efabd7f.jsonl`
