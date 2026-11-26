# 80 · 修复范围与验证收尾（R-WRK）

> 处理审查意见、修复回归或在共享环境做验证时使用。

## R-WRK-01 核实审查意见后确定修复目标

- **内容**：对照当前需求、基线与受影响的调用路径，核实审查意见声称的触发条件和影响。需要运行时信息才能下结论时，选择能区分这些解释的验证。修复后检查原先失败的行为。
- **为什么**：照着评语改可能把需求允许的行为当成回归，也可能把旧问题误归给新改动。核实后才能选对修复目标。
- **坏例**：
```text
reviewer 提了 7 条，全部照改；改完只 build 通过就回复"已修复"。
```
- **好例**：
```text
7 条 → 3 条确认为真（附 base 对照与可达调用链），2 条仅需文档化，2 条判为 churn 不改；
改动后重跑：crc_block_copy_batch_test 23 passed / crc_copy_benchmark_test 1 passed。
```
- **判定**：已修复、已过期或证据不足的意见是否各有依据。验证能否让原问题在修复前后表现出差异。
- **证据**：
  - `dsh/session-0b8eb0fa` Turn 37：「多个 agent 判断并 review 下这些问题是否真实存在，如果真实存在的话就设计方案修复一下，修复完记得把 ut 重新都跑一遍确认通过」｜raw: `/home/baowending.bwd/.dsh/sessions/--home-baowending.bwd-new-RTP-LLM-github-opensource--/session-0b8eb0fa-7da5-4386-bb5e-00562a9c331d/session.v4.jsonl.zstd`

## R-WRK-02 针对已确认的失败选择改动范围

- **内容**：每项修改应能对应到已确认的失败或完成修复所必需的前提。如果原方案的关键假设已被证伪，重新检查在基线行为上实现同一目标需要哪些改动。
- **为什么**：在错误假设上不断叠加保护条件，会留下更多需要维护的路径。反过来，一个看似很小的修改若遗漏了直接关联的调用者，问题也没有修完整。
- **坏例**：
```text
CRC copy 失败处理引入了回退问题，又给新分支添加多层保护，原有回退条件是否正确还没有查清。
```
- **好例**：
```text
回到原调用链，检查 streamresource 的判断是否导致误走失败路径。
若调整这个判断就能恢复契约，验证该条件及相邻正常路径，将修复集中在这里。
```
- **判定**：能否逐项说明它解决的触发条件。方案所需的假设是否仍成立，相关调用者是否保有原有契约。
- **证据**：
  - `dsh/session-456f2d53` Turn 9：「你先把上面我们说的这真的有问题的地方改一下」｜raw: `/home/baowending.bwd/.dsh/sessions/--home-baowending.bwd-RTP-LLM-github-opensource--/session-456f2d53-cae2-4086-94ee-d14f3ef32b16/session.v4.jsonl.zstd`
  - `claude/775dda99` Turn 1：「Do not invent failures or add speculative defenses.」｜raw: `/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/775dda99-310c-4cda-9cc7-7cbf04f91e3e.jsonl`
  - `remote106/codex/2026-10-14T15-23-03` Turn 1（经 agent 转述）：「那看上去我们为了 crc copy 失败的处理，确认引入了问题」｜raw: `11.161.48.106:/home/baowending.bwd/.codex/sessions/2026/10/14/rollout-2026-10-14T15-23-03-01a1394b-11b2-78c1-bf83-c5c2c9e2f564.jsonl`
  - `remote106/codex/2026-10-14T15-48-40` Turn 1（经 agent 转述）：「听上去就是把 streamresource 里的判断删掉就行」｜raw: `11.161.48.106:/home/baowending.bwd/.codex/sessions/2026/10/14/rollout-2026-10-14T15-48-40-01a13962-84bd-7271-950b-99aaa6e6bcad.jsonl`

## R-WRK-03 将无关改动和既有工作排除在交付范围外

- **内容**：比较任务开始时的状态与最终交付，区分本次修复、他人已有改动和工具生成的文件。检查测试门槛、流水线、依赖或样本变化是否确为本次修复所需。
- **为什么**：放宽门槛或换掉测试输入可能掩盖原缺陷。把已有改动一起提交或回退，还会影响其他人的工作。
- **坏例**：
```text
# 为了让 CI 快点绿
fast-fail: true                 # 用户明确说过不要改
gitlink: c43de883              # 与本次改动无关的指针差异，顺手提交
ConfigModules.h 的三处对齐      # 与任务无关的格式改动混进 diff
```
- **好例**：
```text
核对这次 CI 修复的差异，fast-fail 配置与无关 gitlink 都不属于修复。
提交此次代码修改，保留工作区里他人已有的改动。
```
- **判定**：每项交付能否追到本次目的。如果原失败条件或验证门槛改变，是否有产品或测试契约的依据。
- **证据**：
  - `codex/2026-10-20T18-57-51` Turn 8：「对了，记得不要把内源配置的 fast-fail 改成 true，不好」；Turn 20：「然后看看你有改这部分内容吗」｜raw: `/home/baowending.bwd/.codex/sessions/2026/10/20/rollout-2026-10-20T18-57-51-01a158f5-e1d2-7f13-918e-8dc5ddb08f35.jsonl`
  - `claude/da5780f8` Turn 3：「those existing future-work gaps are not regressions introduced by this diff.」｜raw: `/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/da5780f8-d4c1-4cc8-90e2-2afa4fd9afc2.jsonl`

## R-WRK-08 在任务结束时核对临时资源的归属和释放

- **内容**：运行验证或复现时，记录任务额外占用的共享资源和修改的持久设置。按各自的所有者和约定，在成功、失败和中断时释放资源、恢复原值；要保留现场时写清还有谁在使用它。
- **为什么**：残留的服务和资源锁会干扰下一个任务。把状态一律恢复成预设默认值，也可能覆盖其他使用者原来的配置。
- **坏例**：
```text
独占 GPU 运行测量后直接结束，独占设置仍然生效。下一位使用者无法按原方式共享设备。
```
- **好例**：
```text
开始测量前确认此次使用的 GPU 并记录原计算模式。
退出测量时恢复该模式，核对设备状态并停止本次启动的临时服务。
需要保留的实验结果移到约定位置，再释放此次申请的临时空间。
```
- **判定**：任务引入的临时资源是否仍占用，其他使用者的原状态能否恢复，承诺保留的结果能否继续访问。
- **例外**：共享服务或仍有他人使用的资源，按归属交接。
- **证据**：
  - `remote106/codex/2026-10-16T10-30-39` Turn 1（经 agent 转述）：「验证性能时候用 sudo nvidia-smi -i 0 -c EXCLUSIVE_PROCESS 锁卡，验证完结束」｜raw: `11.161.48.106:/home/baowending.bwd/.codex/sessions/2026/10/16/rollout-2026-10-16T10-30-39-01a1428c-1703-7cf0-bd33-29b7ec773b7e.jsonl`
  - `remote106/codex/2026-10-15T20-11-23` Turn 1（经 agent 转述）：「如果 ckpt 从 3fs 读取慢的话，考虑用 modelscope 下载一个到本地，用完删除」｜raw: `11.161.48.106:/home/baowending.bwd/.codex/sessions/2026/10/15/rollout-2026-10-15T20-11-23-01a13f79-6602-7182-90e1-67184487ab23.jsonl`
  - `remote106/codex/2026-09-24T16-07-01` Turn 1（经 agent 转述）：「不是，哥，代码库乱完了，整理一下」｜raw: `11.161.48.106:/home/baowending.bwd/.codex/sessions/2026/09/24/rollout-2026-09-24T16-07-01-01a0d274-21c5-7c93-9343-c5f6685a72c0.jsonl`
