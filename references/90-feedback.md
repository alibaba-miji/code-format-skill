# 用户代码意见后的漏检复盘

用户每次指出代码问题或表达修改偏好，都在处理该意见时检查本 skill 为什么没有命中。先判断意见与当前支持路径是否相符，再改代码和规则；不为了证明 skill 有用而把偏好写成运行时 bug。

下列案例按发生时的版本和约定记录，历史编号的现状见[通用规则清理](#通用规则清理)。当前审查按[规则索引](00-index.md)选卡。

## 已核对案例：启动筛卡修正配置后回到既有流程

来源：当前会话 `01a1f28b-91db-7bb0-9891-0bb77fc96ebb`，2026-11-19，Turn 未核实；来源为本轮用户可见消息，尚未定位 raw 行号。用户依次指出「这里的4简化成max(4, tp_size)不就一步到位了嘛」「配置都是一样的，broadcast设置一个超时推出就行」「筛选卡只是修改配置，最后会回归到原有流程的」。

此前方案按 4 枚举后再过滤 TP，增加全组配置摘要确认，并把筛卡扩展到后续模型 ready、warmup 的独立协调协议。修订改为按 `max(4, TP)` 生成候选（明确 TP 与 4 的整除前提）；沿用同组配置一致的部署约定，仅对 CPU 同步设置超时；选中进程应用配置后汇入原有启动代码，未选中进程才转 fake。无可行规模时全组失败、错误指标、物理设备与端口保留仍然必要，不能在简化时删去。

本轮读取 R-MIN-01/07、R-CFG-02、R-OWN-14 及反馈入口。既有规则已经覆盖信任已明确的前提、限制新增机制和职责边界，缺口在原方案把配置预处理扩大成了服务生命周期管理；不新增通用规则，也不把“所有项目均无须配置校验”推广为规范。本次仅修改设计文档与发布 HTML，未实现业务功能；数字示例和图的汇合关系核对不能代替 GPU 验证。

### 后续核对：三个字段不等于三个环境变量

来源：同一会话 `01a1f28b-91db-7bb0-9891-0bb77fc96ebb`，2026-11-20，Turn 未核实。用户截图指向 `DistributeConfig` 新增的三个字段，问「为啥加了三个环境变量啊」。

读取当前 `gang_group_args.py`、`RankSelection.apply` 与父/子进程消费点后确认：只有 `ENABLE_STARTUP_RANK_SELECTION`（功能开关）和 `STARTUP_UNHEALTHY_RANKS`（按此前要求用于测试故障注入）绑定 CLI/env。`rank_selection` 没有环境变量入口，是筛卡完成后写入的运行时方案，供父进程及 frontend 等消费，不由用户填写。三个字段挨在配置类中，首次说明未展开配置输入与运行时结果的区别，容易误读；不能据此认定存在第三个环境变量或未经核实就删除状态。

本轮读取 R-CFG-01/03 与反馈入口；既有配置单一来源、默认值与职责核对规则足够，不新增规则。本轮只解释实际绑定、数据来源及用途，不改业务代码、不把问题扩展为未要求的重构。后续类似追问先核对参数注册，再区分部署开关、测试注入和运行时结果。

### 后续契约变更：启动前健康检测与 mock 共用环境变量

来源：同一会话 `01a1f28b-91db-7bb0-9891-0bb77fc96ebb`，2026-11-20，Turn 未核实。用户明确变更设想：「把gpu的健康的检查放在start_server之前，通过env来配置哪些卡是健康的（没有检查的时候不配置）这样mock路径和正常路径就是一摸一样的」。

这是新契约，不把此前 bool 输入加测试故障注入追认为运行时 bug。本轮实际读取 R-MIN-03/04、R-OWN-05/13/14/15、R-CFG-01/02/03、R-TST-01/02/03 及本反馈入口。现有规则已覆盖入口单一来源、默认与空值区别、调用链同步，无需新增规则。按新要求移除测试专用坏卡变量与 BackendManager 的健康 bool 入参；入口解析本机健康 CUDA ordinal 列表，下游仅按原 local_rank 判断。未设置为 None（默认全健康），显式空字符串为 []（本机全不健康），非法格式在解析边界拒绝。真实检测和 mock 均在启动前设置同一输入，不添加第二条检测分支。

复核覆盖配置日志、序列化、mock 签名与方案图；测试使用真实参数解析和 TCPStore，按两节点本地编号验证选卡，并保留无可行方案全组失败及一次 error QPS 断言。GPU 检测算法仍由外部提供，本轮不扩大为检测器实现或 GPU 冒烟。后续核对此类改动应先确认输入坐标系与未设置/空集合语义，再同步所有配置消费点。

## 已核对案例：由 VIT 模式和端点决定是否接受多模态请求

来源：会话 `01a1e774-4aa6-7483-9915-f2b7c4257ca1`，2026-11-18 10:52:36（Asia/Shanghai），Turn 未核实。用户指出 `f7c4594158bf661b26504196678d225d0ca76c43`「不需要增加环境变量，而是 vit_sepration = 2 并且 vit_domain 为空的时候，对 vit 请求直接报错，并且不阻塞服务启动」。raw: `/home/baowending.bwd/.codex/sessions/2026/11/17/rollout-2026-11-17T14-25-07-01a1e774-4aa6-7483-9915-f2b7c4257ca1_01a1e82e-4179-7160-9dc3-05a375861f08.jsonl` 第 1510 行。

原实现用 `FRONTEND_ENABLE_MULTIMODAL` 控制请求校验和 VIT 就绪依赖，功能可以工作，但为本次需求增加了独立配置、透传和测试。源码已有 `get_backend_role_list`：只有远端 VIT 模式且配置了 `vit_domain` 才要求 VIT 就绪。因此新约定直接复用已有 `remote_vit` 和后端角色列表，在请求校验入口拒绝缺少 VIT 端点的多模态输入；移除新增开关，不另存派生状态。配置了 VIT 域但暂时没有健康实例时，仍保留原有等待行为。

本轮实际读取 R-MIN-01/03/04/07、R-OWN-01/02/13、R-CFG-01/02/03、R-TST-01/02/03 与反馈入口。现有最小实现和配置规则已足够，不新增通用规则。此前读取记录未完整核实，无法区分未读与误判；本例记录为用户明确收敛配置契约后的设计简化，不把旧实现描述为运行时错误。复核同类修改时，先检查已有模式和端点能否表达需求，再决定是否增加独立开关。

新测试在旧实现上复现单条和混合批次多模态请求未被拒绝；修复后覆盖文本转发、流式与非流式错误、已有 VIT 域和本地模式，以及缺少 prefill 时仍不可就绪。执行证据保存在 `/tmp/frontend-vit-domain-20261118/`，只代表本地 Python 回归，未重新打包或发布线上服务。

同一会话 2026-11-18 的后续 review 中，用户指出「500 就 500 吧」。`8be58a31cd` 虽然撤销了配置开关，却仍为同一个异常增加 HTTP 422 映射和批量接口的专门捕获。上一轮已读 R-MIN-07，但只简化了配置，漏查了接口层的改动。现在撤回映射、捕获和对应测试，保留路由前拒绝请求的功能。空 VIT domain 从就绪角色中排除的条件已在父提交 `59b4180281` 中，无需再写一次。

## 已核对案例：THP 临时启动注入转为正式配置

来源：当前会话 `01a1e39f-c10c-7022-a714-b10d57486898`，2026-11-17（Turn 未核实，尚未定位原始日志行号）。用户要求「设置一个DISABLE_THP环境变量，maga_start读到他运行一段脚本禁用，现在这个东西可读性太差了」。

原方案为隔离环境验证，在 CMD_BEFORE_START 中把 base64 Python 包装追加到 NUMACTL_PREFIX；它已完成进程 THP 禁用，但不适合作为长期配置。此次是用户明确要求将临时验证方案落入代码，不把此前已验证的方案追认为运行时错误。读取 R-MIN-02/06/07、R-OWN-06/14/15、R-CFG-01/02、R-TST-01/02/03/05 后，既有规则已覆盖入口配置、职责分离与调用路径一致性，无需新增通用规则。

实现采用 maga_start.sh 解析 DISABLE_THP，独立脚本调用 prctl 后 exec 服务，THP 启动包装与 CPU 绑核前缀分别维护；默认启动和 CMD 路径同步覆盖。验证使用本机轻量子进程读取 /proc 状态，不以单独运行后退出的脚本冒充服务继承成功。业务发布与本地代码验证分别报告。

## 后续方案评估：采样准备契约统一到 Sampler

来源：主会话 `01a1c90c-cc18-7063-8df2-30bdbddc6977` 第 7709 行，2026-11-13T07:17:05.977Z，Turn 未核实。用户要求先评估另一个 session 的方案能否让代码统一、简洁，并指出此前设计不合理。raw: `/home/baowending.bwd/.codex/sessions/2026/11/11/rollout-2026-11-11T13-20-21-01a1c90c-cc18-7063-8df2-30bdbddc6977.jsonl`。分享页无可读正文；实际读取本机同主题会话 `01a1d2e6-0e78-7b13-9cc6-5d01201d4892` 的最后两轮公开消息，未验证分享 ID 与本机会话 ID 的映射。

当前实现仍让 SamplerInputs 同时持有原始字段和 greedy_params；CUDA 在外部 prepare，ROCm 在 op 内扫描 host 参数、上传和推进 RNG；packed helper 又原地改写两组字段。把调用放到同一边界不等于消除重复状态。此前已读 R-OWN-14/15，却只核对分支在既有契约下能否工作，没有充分检查准备责任能否统一，属于规则读后落实不完整；本轮也重读相关卡片和反馈入口，现有规则充分，不新增重复规则。

新方案将 SamplerInputs 保持为原始输入，GreedyParams 作为 forward 内局部执行参数；CUDA/ROCm 共用 prepare，再做可选 gather、sampleOp、scatter。这是本项目职责边界的进一步调整：通用行映射由 Sampler 编排，底层 sampleOp 仍不感知 MTP。不能再套用前述“映射完全不进入 Sampler”的旧项目约束，也不能声称旧实现因此必有数值 bug。执行时还须明确 host/device 字段契约，按完整行预留 RNG 后直接裁剪，只物化需要的 history 并重新绑定指针；通用 scatter 处理无概率输出，模型布局和 mask 共享缓冲生命周期不迁入 Sampler。ROCm 的执行布局变换与拒绝采样能力限制不能当作重复准备直接删除。

本轮仅源码评估，未改生产代码或运行测试。公开方案、源码依据和裁决见 `/home/baowending.bwd/packed-sampling-work/unified-sampler-plan-evaluation-20261113/assessment.json`。此前 CUDA UT 通过不代表新统一契约或 ROCm 已验证。

## 已核对案例：并发故障链路要保留在正式 DashSc UT

来源：本会话用户可见消息，2026-10-29（Asia/Shanghai），Turn 未核实。用户要求「你ut要确认都复现问题。在dashsc层的ut」，并明确「模拟一个dashsc server收到请求，另外一个请求刚好遇上了这个case」。

此前正式测试分别覆盖 Master 共享 channel 隔离和 DashSc 取消终态；两个并发请求穿过 DashSc 的组合只保存在临时 smoke 中。临时脚本的红绿对照能支持当时的诊断，但没有为后续提交保留同等的正式回归保护。本轮已读 R-TST-01/02/03、R-MIN-02/07；规则足够，缺口在测试落地范围，不新增重复规则。

正式 inference UT 现在用同一个 DashSc server/stub、真实 BackendRPCServerVisitor 和 MasterClient 发起两个请求。B 先进入 Schedule 等待，A 收到真实 gRPC RESOURCE_EXHAUSTED；A 经生产 domain fallback 返回503业务帧并结束后，检查 B 的服务端 Schedule 尚未退出、共享 channel 未替换，再释放 B 并检查客户端 token、EOF、OK及流清理。不能只检查 B 的外层 call 仍 pending：旧版静默挂死也符合这个条件。只隔离服务发现和模型计算，不模拟取消、错误映射或 channel 行为；已有 owner-close 回归也改为经过真实 BackendRPCServerVisitor。

正式两类 RPC UT 加载旧完整生产模块 `9c1d48b65f` 时，6项缺陷回归失败、5项正常取消/停服/完成对照通过；当前 `f0446e372b` 生产代码加未提交测试改动时，11项通过。不能要求兼容性对照也在旧版失败。相关五模块另实跑301项与125个子测试通过。测试源码hash、工作区diff和逐项结果保存在 `/tmp/channel-dashsc-ut-20261029/`；这些不是线上灰度或GPU推理证据。

## 已核对案例：阻断共享连接误关不等于保证上游终态

来源：主会话 `01a1819f-6539-78d3-bd42-95404cd46406`，2026-10-29 14:47:46（Asia/Shanghai），Turn 未核实。用户问「请求挂死又是什么问题呢，如果真的出现 `MasterClient.close()` 等情况，是不是也得避免请求挂死」。raw: `/home/baowending.bwd/.codex/sessions/2026/10/28/rollout-2026-10-28T16-27-49-01a1819f-6539-78d3-bd42-95404cd46406.jsonl`，第 2256 行。

意见成立。当前补丁阻止单请求失败关闭共享 channel，却保留合法 owner close。此前 owner-close 测试只证明 pending Schedule 收到 CancelledError，没有证明外层 ModelStreamInfer 客户端收到终态。真实入口 `rtp_llm/dash_sc/inference/servicer.py:2399` 对 BaseException 记录后重抛；异常退出和 access log 完成不等于 gRPC 流已结束。不能将这个局部修复称为所有取消路径的完整挂死修复。

本轮用当前完整 MasterClient 模块与 grpcio 1.62.0 实跑五个最小双向流桥接场景。上游仍活着时单独调用 owner close，handler 已退出，但观察 0.3 秒后客户端 read 仍 pending、RPC 未 done；测试主动取消清理。桥接入口显式 abort(CANCELLED) 后，客户端收到非 OK 终态。真实 peer cancel 仍为 CANCELLED；server.stop(0) 无论是否增加该处理都以 UNAVAILABLE 结束。正常停服不能被笼统说成必挂。peer cancel 和内部取消时 context.done()/cancelled() 实测均可为 False，不能用这两个 False 判断取消来源或把内部取消擅自标成用户断连。

本轮实际读取 R-MIN-02、R-TST-01/02/03、R-REV-08/14。已有规则要求调用方可见的失败和真实测试边界，规则充分；前轮将下游任务结束等同上游请求结束，属于验证范围与结论不匹配。本次只补复盘，不新建重复规则。后续修复需在真实 RPC 边界保证非 OK 终态，并补 owner close、真实用户取消、deadline、输出中途取消及正常停服测试，不能只直接迭代 generator 断言 CancelledError。

诊断脚本 `/tmp/master-close-terminal-repro-20261029.py`，结果 `/tmp/master-close-terminal-repro-20261029.log`。本次只隔离不可用 C++ 导入，生产 MasterClient 未替换；frontend 是最小桥接，不是完整 DashSc、GPU 或线上回放。五项运行完成不代表正式边界修复已实现；仓库补丁仍为 `a3626c1ef9bc63197994c8264880fc0b057f032df9147d9d6c706163e2b88ffa`，未修改生产代码。

后续用户明确要求「设计一个方案并且开发+ut」，已实现 inference/proxy 两个真实入口的显式 abort(CANCELLED)，原始异常保留给日志和 trace，取消文案不再归责 peer。最终补丁 SHA256 为 `864d683d478aaf819d3e94438879dac6f697bd3c29aec31658ced37821796a05`。新增 10 个真实生产 servicer RPC 用例和 1 个分类用例，连同 3 个既有边界用例共 14 项与 2 个 subtests 通过；同一最终 RPC 测试加载旧入口后 5 项因上游 read 超时失败、5 项正常取消/停服/完成对照通过。广泛运行 300 项中 291 项与 125 个 subtests 通过，9 项被真实 C++ MMPreprocessConfig 不可用阻塞；旧完整生产模块复跑同样 9 项环境失败，未伪造构造器或写成全量通过。本地独立 reviewer 复核最终实现无可行动问题，未将旧三模型 review 追认为新补丁已审。方案、测试日志和验证边界见 `/tmp/dash-terminal-ut-20261029/design.md`、`/tmp/dash-terminal-ut-20261029/validation.md`。

## 已核对案例：历史修复的结果类型与真实主备测试

来源：主会话 `01a1819f-6539-78d3-bd42-95404cd46406`，2026-10-29，Turn 未核实。用户问「我们的fix和`3738ed3774` 哪个更优雅」，并要求历史方案更好时采用、检查测试补全。raw: `/home/baowending.bwd/.codex/sessions/2026/10/28/rollout-2026-10-28T16-27-49-01a1819f-6539-78d3-bd42-95404cd46406.jsonl`，第 2022 行。

固定基线 `9115e23`：两种方案都移除单请求失败时对共享 gRPC channel 的关闭。历史提交另用两个 dataclass 包装 protobuf 与无响应；当前只有这两种返回状态，deadline 和取消仍抛异常，所有调用方均正确判 None。包装类型未增加错误信息或处理能力，不能仅因类型数量更多就判为更好；也不能将本例推广为 Optional 总优于结果类型。本轮保留最小修复，补 `Optional[FlexlbScheduleResponsePB]` 注解。

历史测试经过公开入口验证真实主备重试，这一点值得采用。原六项真实 RPC 测试覆盖私有方法的并发隔离，但主备测试以 mock None 注入失败，缺少二者组合。本轮追加主失败备成功、主备均失败、业务拒绝不重试三个真实双服务用例，用 Event 固定并发，不 mock 被测路径。旧基线的新三项为 2 失败、1 通过；全部隔离用例旧基线 5 失败、4 通过，修复后 9 通过；两个相关模块共 37 用例与 20 subtest 通过。四个旧基线绿灯是契约对照，不能宣称全部用例都证明旧缺陷。

本轮读取 R-MIN-02/04/07/08、R-OWN-01/13、R-TST-01/02/03、R-REV-04/05/08/14。现有规则充分，用户比较不构成旧实现错误；组合测试覆盖不足已补，本次只留复盘，不新增规则。主 agent 和独立本地 reviewer 均核对最终增量；CPU bootstrap 仅隔离不可用的 C++ 导入，真实 Python/gRPC 路径执行，不冒充 Bazel、GPU 或完整线上回放。证据与最终 patch 位于 `/home/baowending.bwd/RTP-LLM/build_logs/schedule-channel-cancel-fix-20261029-comparison/`，SHA256 为 `a3626c1ef9bc63197994c8264880fc0b057f032df9147d9d6c706163e2b88ffa`。

## 已核对案例：xgrammar 超时状态与批次耗时

来源：session `01a1679e-1e67-7672-8d91-6e7bdcd8c3be`，2026-10-26，Turn 未核实。用户问 `_positive_int` 的捕获是否必要、P→D 是否需要传递 timeout，并要求 processor 只在超时时上报 QPS；随后明确「generatestream只应该读」，接受 P/D 各自判断超时，选择 RT 统计「本轮整批 CPU 状态更新耗时（推荐，串行更新也统计）」。raw: `/home/baowending.bwd/.codex/sessions/2026/10/26/rollout-2026-10-26T14-50-04-01a1679e-1e67-7672-8d91-6e7bdcd8c3be_01a176f9-2ed3-7ee1-8116-8e3427907aaa.jsonl`，原话及行号保存在 `/home/baowending.bwd/xgrammar-work/01a1679e-1e67-7672-8d91-6e7bdcd8c3be/feedback-20261026/user-feedback.json`。

固定旧版 `487d02cd07` 的核实结果：

- 捕获有真实语义。`EnvArgumentParser.parse_args` 在混合 CLI/env 入口吞掉 `ValueError`，却将 `ArgumentTypeError` 作为启动错误。直接删捕获会让 `GRAMMAR_UPDATE_TIMEOUT_MS=invalid` 静默回落到默认值。保留实现；不能只凭标准 argparse 的行为判冗余。已有 R-MIN-01/02、R-CFG-03、R-TST-01/02/03 覆盖，无需新规则。
- P 确实在产出首 token 后推进 matcher，D 原来确实读取 marker。外部 disable 的唯一生产调用在 D 入队前，未证明有异步竞态。用户明确接受 D 独立推进和判断后，删除 request marker 及两层外部 setter，保留原来的 P 推进和响应 aux 字段。这是职责与端间语义的明确取舍，不能写成旧代码必有数据竞争；适用 R-OWN-05/11/15、R-MIN-03/07。
- 逐 processor 报 RT 的采样数随 batch size 增长。新要求改成批次 CPU 更新的 wall time，timeout QPS 仍由 processor 首次超时上报。主 agent 起初选了外层 `AsyncRunner::sync`，独立复核指出该测点遗漏关闭外层 async、开启内层线程池的可达更新；用户进一步选定本轮整批耗时后，撤回外层计时。最终在 Normal dispatcher 提交 CPU 任务前开始、所有 worker 完成后结束，MTP 在整批 `updateStreams` 周围计时；串行也统计，已有 D2H 准备在计时前。不能把上一轮剩余等待与本轮更新 wall time 混称为 grammar CPU 总耗时。

本轮实际读了 20/30/40/50/60 相关正文，复核补读 R-REV-02/04/05/06/08。R-STA-01/07/08/11 已覆盖统计归属、额外同步和口径；这里补 R-STA-11 的延迟采样粒度与嵌套异步边界判据，不新增重复规则。此前 review 的读取记录不足以证明曾评估逐流 report 开销，不补造「已读后误判」的历史。用户的批次统计和只读 stream 接口要求作为本项目当前约定保留，尚未实测的吞吐收益不写成性能数字。测试与独立复核结果绑定当次补丁，保存在同一 feedback 目录；撤回的外层计时不计入最终验证。

## 审查纠错案例：输出桥缺字段不证明生产请求可达

来源：session `01a1679e-1e67-7672-8d91-6e7bdcd8c3be`，2026-10-25，Turn 未核实。用户要求确认 diff 可见性，并在外部三模型 review 后追加三个 subagent 自行 review。用户没有指出下述 bug；它是本次 integration reviewer 提出的候选，主 agent 曾采纳，补查完整入口后撤回。

固定基线 `aa1d38c87a232fd8c4599e7a10dcf909c99194f7` 的 C++ OpenAI 同步 final 桥没有透传 aux_info。初轮据此推断 `extra_configs.regex` 请求在 grammar 超时后会丢标记，但漏查了 enqueue 前的 `render_chat_request → getRequest → ChatCompletionRequest` 校验：before validator 拒绝全部嵌套 grammar 字段，C++ 请求类型及配置提取也未编译顶层 response_format。Factory 只从四个 typed grammar 字段创建约束。因此，该入口不能产生候选问题所假定的 timeout 请求。

R-REV-02/04/05、R-MIN-01/07、R-OWN-15 与 R-TST-01 已要求可达触发链和测试边界，规则与路由足够。三个 reviewer 的任务书与读取产物保存了正文读取记录；integration 初轮和主 agent 的错误属于读后未追完输入校验。contract 复核桥接实现时沿用了未证实前提，后来也独立撤回。人工注入 timeout=true 的 24 项桥接测试只证明传参和序列化，不证明真实 HTTP 入口可以启用 grammar。

本次只补纠错记录，不新增重复规则。后续此类审查先检查请求校验、配置转换、factory 和真实调用者，再判断输出桥是否遗漏支持路径。5 个尝试修改文件已精准恢复，最终 35 文件补丁 SHA256 为 `f4f96b34668681e04a15ca8991767e23f36530b7a120a1fc9251830749010a23`，恢复后两个目标重新执行共 22 项通过。尝试版本的记录保留，不能计入最终版本。证据目录：`/home/baowending.bwd/xgrammar-work/01a1679e-1e67-7672-8d91-6e7bdcd8c3be/self-review-20261025/`，包括 `root-audit.json`、两路 `fix-1/answer.md`、`restoration-proof.json` 和 `final-test-evidence/manifest.json`。

## 已核对案例：最终按 feature 整理时检查中间提交

2026-10-24，用户要求两仓 rebase 后用三位本地 subagent 和外部模型重新 review，并额外检查“commit 按照 feature 拆分是否干净”。本轮固定公共版本 `4a7c9d905f`、父仓 `e323856687`。三个本地 reviewer 都读到了 R-DIF-02；检查中间节点后发现 startup 新测试的 device 依赖晚一个提交才加入、monitoring 夹带 grammar shutdown，runtime 的旧测试修正又留在 planner 清理提交。最终 HEAD 已包含这些修正，但中间 feature 节点仍不完整。

R-DIF-02 已有功能粒度和独立测试要求，主要缺口是例外段把“已被 review”与“已合入”一并绝对禁止重写，与用户本次明确的未合并分支整理授权冲突。本轮先保存评审 SHA、patch、backup refs 和远端 OID，再分离 grammar、将监控跳过策略并回 monitoring、将 planner 退役和测试修正并回 runtime、将 device 依赖并回 startup。新测试需求单独提交。公共生产树整理前后相同；父仓先同步公共基线，再逐 feature 更新引用。每个候选提交做了依赖和源码检查，这不等于逐提交编译通过。

本次补充 R-DIF-02 的授权边界和上述真实案例；不新增重复规则。旧评审是否在当时读过提交拆分正文没有完整证据，不归因为“模型一定漏读”。下轮需同时核对最终树、各功能引入点的 BUILD/测试契约，以及两仓对应关系。证据目录：`/home/baowending.bwd/eplb-work/01a16309-49be-7181-970b-abfa99b86c2f/rebase-20261024/feature-candidates`。本机安装链接与 `04_skill` 源文件相同，更新后运行索引生成和规则校验。

同轮继续按调用链追依赖，又发现 `27246577` 已把 V4.1 full-model smoke 注册到 x86 suite，但所需 FlashMLA wheel 和 indexer ABI 适配直到 `8f330eec` 才就绪。这里不能只检查 Python import 或 BUILD label 存在：应将 x86 smoke 的可执行目标与 suite 注册后移到 x86 kernel feature。MoE-only UT 使用原有 DeepGEMM，不依赖该 FlashMLA/indexer 路径，可以留在 V4.1 feature。本轮 reviewer 确实读过 R-DIF-02，这次属于依赖路径核对不完整；补这项判定，并同步入口的 amend 例外摘要，避免正文已修但入口仍给出绝对规则。

## 怎么归因

先定位真实问题代码和用户原话，在 `00-index.md` 找候选，再读规则正文。用本轮实际读取记录判断：

| 归因 | 能支持结论的证据 | 更新位置 |
|---|---|---|
| 缺规则或缺案例 | 当前规则没有覆盖该约束，或现有例子无法区分好坏 | 有同义规则就在该卡补真实坏例、好例、适用边界和来源；确实独立的新约束才新增卡 |
| 入口未加载 | 工具记录未加载 skill，或安装/发现入口缺失 | 修复安装、触发描述或上层 review 提示，不复制规则 |
| 路由漏读 | 读了入口或索引，但未读相关卡片正文 | 改 `SKILL.md` 的领域路由或 reviewer 读取清单，补明确的触发词 |
| 读过后误判 | 记录证明读过正文，却错误套用例外或遗漏实际调用路径 | 收窄或澄清判定/例外，用这段实际代码补对照案例；要求复核该触发路径 |
| 需求变化或项目偏好 | 新要求替代历史约定，或正确实现之间的职责/接口选择 | 记录当前约定、适用项目与来源；不宣称旧实现必有 bug，不污染通用规则 |

缺少读取记录时写「无法区分未读与误判」，不要补写虚假的读取历史。可证明的入口或路由缺口仍可修复。一次反馈可以有多个原因，但分别列证据。

## 这次要留下什么

在当次 review 目录的裁决记录中留下：用户原话与来源、问题代码/commit、命中的规则 ID、实际读取证据、归因、改了哪个规则或入口、如何验证。源规则没有变化时也要说明原因。不要把整段会话、凭证或无关信息复制进 skill。

新增证据使用已知 session id、时间、消息定位或 `raw:` 路径；Turn 不知道就明说。修改完成后重建索引并跑 `tools/check_rules.py`；改了入口再跑 Codex skill 的 `quick_validate.py`。验证只证明文件和索引结构正确，是否真的能命中要用原问题代码重新审查。

## 已核对案例：记录后清零的归属

来源：用户在 session `01a15d3e-ab06-7732-ba3b-af0098e8b866`、2026-10-22 16:47:05（Asia/Shanghai）要求把 `beginStep` 改成 `clearRecordBuffer`，正常路径放进 `recordStep`，warmup 在 `else` 中单独清零。原文定位见 R-OWN-11 新增证据，Turn 未核实。代码范围是 EPLB `ExpertBalancer::step` 与 `ExpertLoadMonitor::recordStep`，最终提交 `00491063202c0cccfedbbc018954daaf428a778e`。

这不是缺一条新规则：R-OWN-11 原有好例已要求 `recordStep` 内统一清零，R-STA-01 也已有「record 后清理」证据。旧实现按先记录、后清零顺序执行，不能据此报告已经污染指标；本次改动收敛正常路径的职责，并让只清零的 warmup 路径显式保留。

本次安装前 `~/.codex/skills/code-format-skill` 不存在；可核对的旧 review 记录未提供已读这些规则卡的证据，无法把原因定成「读过后误判」。入口缺失可确认。此外，review 路由原先只笼统要求按领域读取，而 R-STA-10 的旧示例还使用 `beginStep`，容易漏掉 R-OWN-11 的组合判断。

处理：安装单一来源入口，review 路由明确读取所有权及状态相关卡片，R-OWN-11 换成真实正常/warmup 对照，R-STA-10 同步清零归属。规则总数仍为 74，不新增重复规则。后续 review 把实际读过的文件和规则 ID 写入记录，才能区分漏读与判定失误。

## 已核对案例：有 target/draft 快照不等于 commit 已排除

来源：session `01a15d3e-ab06-7732-ba3b-af0098e8b866`、2026-10-22 17:43:56（Asia/Shanghai），用户问「有实际确认过draft和target model都会汇报监控，且commit阶段不汇报，只汇报prefill/ decode target verify / decode draft propose吗」。Turn 未核实，原话 raw 路径及行 425 见 R-TST-03 新增证据。

本次核对区分了三种证据：旧提交 `e2f98ea23a3a` 的 V4 smoke 有 prefill target 19、decode target 5866、draft 5866 个非零窗口，但 snapshot 没有 phase 字段；`00491063202c` 的双卡 UT 直接构造 monitor、喂入人工计数，不经过 MtpExecutor；当前 `872d8f617a67` 源码的 DSpARK 阶段路由符合预期，而普通 MTP 关闭 graph 后，commit 会回落到启用监控的 `draft_model_`。前两种证据都不能证明「所有 commit 不统计」。源码位置为 `MtpExecutor.cc:920/932/1282/2279`，行号绑定该提交。

已有 R-TST-01/03/05 与 R-OWN-15 已覆盖测试边界、结论与实际执行对齐、分支一致性，不需要新规则。没有当时读取卡片的完整记录，无法区分未读与误判。可以确认的入口缺口是：review 路由此前没有把「是否实际验证」和阶段覆盖问题指向测试规则，既有案例也没说明「角色非零窗口」无法证明「阶段排除」。

处理：补 review 读取路由，R-TST-03 增加组件 UT/无 phase 快照的坏好例，R-TST-05 与 R-OWN-15 增加从 phase 到 wrapper 配置及 fallback 的判定。重审本例必须得到三个不同结论：历史双角色有计数；组件汇总测试通过；普通 MTP eager commit 未被排除。只更新规则与证据，不借复盘擅自修业务代码或扩大测试范围；用户要求 PR 不写验证范围时，本地仍保留证据。


## CI 回查案例：必填参数遗漏初始化别名调用

来源：延续 session `01a15d3e-ab06-7732-ba3b-af0098e8b866` 中要求全仓同步接口、核对其他修改点的 review 任务；本次直接证据是 Aone run `82321628` 的 `test-smoke-sm10x`（job `127632762`）产物，并非新的人类原话。固定开源版本 `e079a0fc659f4d67d870cf81d54f291397eeb202` 的 V4 初始化 `_executor(x, weights, ids)` 漏传必填 `expert_load`，实际报 `MegaMoeSEExecutor.forward() missing 1 required positional argument: 'expert_load'`；V4.1 的 `_strategy(...)` 存在同类遗漏。另有测试把旧 `input_ids` 位置参数绑定到了新增 `expert_load` 上。

R-OWN-13 已要求所有调用点同步，规则不缺；已有审查未覆盖到上述初始化别名，不能把搜新参数名的结果当成旧调用已清空。没有足够历史读取证据，无法区分之前未读与读后遗漏。本轮在 R-OWN-13 的判定中明确追实例/别名以及 `__call__`、初始化预热和 graph 测试，而不新增重复规则、不把整类 MoE 参数改回可省略。

修复在两个生产 prewarm 调用显式传 `expert_load=None`，表示这次 JIT 初始化不记录；测试位置参数改为明确的 `input_ids=...`。回归测试执行真实源码 prewarm 块并 autospec 实际 `forward` 签名，旧源码在 V4/V4.1 × Mega/MegaSE 四个 subtest 均因漏参失败，修复后通过。它验证调用契约，不声称验证完整模型初始化或 GPU kernel。证据保存在 `/home/baowending.bwd/RTP-LLM/build_logs/eplb-ci-20261022/prewarm-fix/`；冻结补丁 SHA256 为 `1d915958101da99f632d028a9f5fa1a9073c05dbf5f287e5007407c6a44dd225`。


## CI 回查案例：列表索引调用漏传必填参数

直接证据：Aone run `82332598` 的 ARM UT job `127655814` 在版本 `483029a1a843dbc6a2f0c648d6319eff03f3c74c` 实跑 186 个目标，仅 `local_loop_cuda_test` 失败。`test_multilayer_prefill_does_not_retain_fp32_workspaces` 的预热仍为 `executors[0](x, weights, indices)`，而 `LocalLoopExecutor.forward` 已要求 `expert_load`。该问题来自 CI，不冒充新的人类原话。

已有 R-OWN-13 在上一轮已读取并补充实例/别名追踪；本次是执行扫描漏掉 AST `Subscript` 调用，不能再归因于未读规则。修复只为这次内存测试预热补 `expert_load=None`，保留全部显存断言，不恢复接口默认值。补充判定明确索引容器与循环别名，规则总数仍为 74。

B300 CUDA runtime SM10.3 复现：旧版该组 9 个用例中 1 个 missing-argument error；修复版 9/9 实跑通过，0 skip。最初外部 launcher 未把 runfiles 路径传播给子进程，另外造成 pydantic 导入失败；修正 launcher 的 PYTHONPATH 后重新做上述对照，不能把环境故障归给生产代码。公开代码只改一行。证据目录 `/home/baowending.bwd/RTP-LLM/build_logs/eplb-ci-20261022/indexed-call-fix/`，补丁 SHA256 `58392d915efaa240d2e7bd8292a78f3543d8bfdace5d3f297ccb3920c2ed1385`。

## 已核对案例：物理路由变化与修改前基线

来源：session `01a16309-49be-7181-970b-abfa99b86c2f`、2026-10-23，用户问「专家自动调度前后，megamoe应该执行的逻辑不一样了？为啥张量还能完全一致」，并明确「golden不一致倒是不用特别在意，只要和修改前一直就行」。Turn 未核实；原话与裁决保存在 `/home/baowending.bwd/eplb-work/01a16309-49be-7181-970b-abfa99b86c2f/user-baseline-feedback.md`。

诊断脚本保存了物理专家编号，但相等断言比较的是还原后的逻辑专家编号、输入和输出；权重同样按逻辑身份核对。原始样本中 144 个物理路由编号全部改变，其中 55 个跨 rank，而逻辑对齐后的结果仍逐位一致。这不矛盾。主 agent 把有限字段的结论概括成“张量全部一致”，遗漏了对齐口径；冻结产物中 `all_recorded_tensors_bitwise_equal` 的名称也宽于实际 `comparisons` 字段。保留旧产物，新增物理路由证据与范围更准确的说明，不回写历史结果。

本轮读取了入口、90-feedback 和 R-TST-01/03/04/05；旧读取记录见任务目录 `rules-read.md`、`user-precision-feedback.md`。技术记录已有逻辑对齐说明，汇总遗漏属于读后执行/表达误判。另一个可确认的规则缺口是 R-TST-05 原好例把“关闭 EPLB”直接称为“基线 commit”，容易将新代码的开关对照误当旧源码实验；此前实际 smoke 正是同一新版本上的 NONE/STATS/ALL，不能证明与修改前源码相同。

处理：R-TST-05 明确旧源码、新源码关闭、新源码开启的三路对照，并要求分别报告物理变化和逻辑结果、披露启动兼容补丁和比较字段范围。本项目按用户要求以修改前实际结果验收，共有的历史 golden 差异单列，不升级为所有项目都可忽略 golden 的通用规则。规则总数仍为 74；重建索引并运行规则校验。旧源码实验另行执行，本复盘不预报其通过。


## 已核对案例：OOM 归因与仍在响应的 reviewer

来源：session `01a15d3e-ab06-7732-ba3b-af0098e8b866`，2026-10-23 10:16:16（Asia/Shanghai），Turn 未核实，原话定位见 R-TST-03 / R-REV-10 新增证据。用户追问 OOM 是否预期、是否由我们引入，并要求 GLM 正常响应时继续等待。

OOM 原判断只依据 PR 多次 host cgroup OOM、监控配置关闭和失败阶段在权重加载，未检查用户给定参考任务的同 target 实际结果。回查 run 81956738 发现 Pro 实跑通过，且 public 源码树与本 PR 基线一致；参数同为 scratch，加载前 RSS 均约 1.9 GB/rank。撤回“确认外部确定性故障”，保留为待归因。R-TST-03 和 R-REV-08 已有证据先行要求；无法凭现存读取记录区分旧判断是未读还是读后误判，但原先没有 host OOM 与基线对照的具体案例。补 R-TST-03 判定、坏好例及入口路由，不新增规则。

review 原 runner 使用 `process.wait(timeout=args.timeout)` 的总时长限制，wrapper 使用最终 JSON 输出，无法用 output.log 判断活性。第 5 次 review 的 GLM 在 240 秒截止前约 68 秒仍有公开工具结果，不能当作卡死。`agent-review` 原 skill 还明确写“单次调用上限”，因此该机制与本轮用户要求冲突，不是模型异常的证明。R-REV-10 既有规则防止把中断算通过，但没有规定如何避免误中断；补充等待判定并把具体机制交回 runner，保持规则职责。

修正：wrapper 流式消费模型事件，只保存最终 envelope 与无正文的进展元数据；runner 默认连续 900 秒无有效进展才停止，无默认总时长/轮数上限。模型增量、工具调用和结果续期，ping/stderr/API 重试不续期；正常响应继续等。15 项真实 wrapper/伪 CLI 进程级 UT 和 13 项报告上传 UT 通过，独立 subagent 复核同样通过；实际 GLM 验证另记录，不用伪 CLI 测试冒充服务实测。记录目录 `/home/baowending.bwd/RTP-LLM/build_logs/eplb-ci-20261022/review-wait-fix/`；OOM 证据与撤回记录在相邻 `oom-recheck-20261023/`。

## 已核对案例：服务默认值从关闭改为按角色自动汇报

来源：session `01a15d3e-ab06-7732-ba3b-af0098e8b866`，2026-10-23 11:04:43（Asia/Shanghai），Turn 未核实，原话及 raw 路径见 R-CFG-03 新增证据。用户要求 CLI `eplb_metrics_report_interval` 默认 `-1`。

这是对此前明确要求默认 `0` 的变更，不能把旧实现或旧审查虚构成漏检。R-CFG-01/03 已有入口、角色解析与优先级规则；本轮已读取正文。补充的 case 是区分服务输入哨兵与 native 归一化边界，并要求测试真实无参数入口、显式等于默认值的 CLI 覆盖环境值。不新增重复规则，也不把项目默认数值升级为通用规范。

首轮修正仅修改 CLI 默认值、帮助文案、参数文档与配置 UT。保留 C++ 默认 `0` 及旧 pickle 缺字段关闭行为：直接 native 构造绕过 `EngineConfig`，而 `ExpertBalancer` 要求非负步数。13 项真实 CPU 配置 UT 通过；负向对照加载旧 CLI 模块后，新默认入口测试按预期失败 `0 != -1`。证据目录 `/home/baowending.bwd/RTP-LLM/build_logs/eplb-ci-20261022/default-interval-fix/`。多模型审查与本轮发布结果另随实际记录，不以此条目预先宣称通过。

随后主 agent 补充追查消费者限制，并交 subagent 核对真实服务组合，发现上述首轮修改尚有回退：`docs/backend/af_disaggregation.md` 明确支持 Qwen3 dense AFD，`qwen.py` 创建 `Qwen3DisaggregateModel`，不走 MoE DeepEP 的拒绝路径。新默认启用后，`ExpertBalancer` 创建 monitor，后者无条件拒绝 FFN disaggregate。第一轮 DeepSeek/Kimi 已读配置规则但只覆盖解析、普通入口和 native 非负契约，未覆盖该服务组合；GLM 当时仍在运行，后来首轮正常完成，独立发现相同的 FFN 构造回退，不能把它归入漏检。此问题是本轮默认变更的审查范围遗漏，与历史默认 0 原本符合用户要求是两回事。

坏例（默认改为启用，却不核对消费者的已有配置）：
```cpp
if (config.eplb_metrics_report_interval > 0) {
    load_monitor_ = std::make_unique<ExpertLoadMonitor>(/* ... */);
    // monitor 构造拒绝 FFN disaggregate，dense AFD 因此新增启动失败。
}
```

修正例（AFD 原本就不支持该监控，由 balancer 内决定不构造；不把能力判断搬到 Python）：
```cpp
if (config.eplb_metrics_report_interval > 0
    && !params.parallelism_config.ffn_disaggregate_config.enable_ffn_disaggregate) {
    load_monitor_ = std::make_unique<ExpertLoadMonitor>(/* ... */);
}
```

新增 `test_dense_afd_does_not_start_monitoring` 覆盖正 interval 下构造、warmup、正式 step 与无 snapshot；planner 既有 FFN 限制保持。普通 dense DP 的 EP 默认在上游推导为 TP×DP，显式 EP1 要求 DP1，不能用手工非法布局伪造回退；dense CP 已有 physical_expert_count==0 的例外。R-CFG-03 补默认启用时的消费者检查，不新增泛化防御规则。第二版源码、真实 UT 与多模型复核以 `default-interval-fix/revision2/` 及 review 记录为准；本条目不预先宣称测试通过。


## 已核对案例：监控范围收敛为 target-only

来源：session `01a15d3e-ab06-7732-ba3b-af0098e8b866`，2026-10-23 11:52:02（Asia/Shanghai），Turn 未核实，行 9027：「把小模型的eplb监控删了，eplb监控只负责大模型的prefill/decode verify阶段；其他阶段均不管eplb，这样的话dspakr和非dspark流程是一样的」。raw: `/home/baowending.bwd/.codex/sessions/2026/10/22/rollout-2026-10-22T17-19-12-01a15d3e-ab06-7732-ba3b-af0098e8b866_01a162e8-4734-7e01-810d-2803cb609841.jsonl`

这是对历史 target+draft 需求的明确修改，不把旧版创建 draft monitor 归为漏检。本轮读 R-OWN-15、R-STA-01/10/11、R-CFG-03 和 R-TST-01/02/03：阶段是否统计由实际 wrapper 的配置决定；普通 MTP eager commit 会复用 propose wrapper，不能只关闭专用 commit wrapper。最小实现为停止向全部 draft wrapper 复制 target 的 EPLB 配置，沿用 native 关闭默认值；target 保留配置。无需新增 executor runtime 判断、phase 标志或 Python 能力位。

R-OWN-15 已覆盖共享 wrapper/fallback 检查，但“同构”例外只列数据布局，可能被误解为 target/draft 必须具备同一能力；补充明确角色职责不同时按需求限定，并要求同一角色的 eager/graph、DSpARK/MTP 入口一致。本次 UT 检查真实 MtpExecutor 构造的 wrapper，不用直接构造 monitor 的组件用例冒充阶段验证。revision3 冻结源码下，真实 wrapper 的 8 个构造组合通过；恢复旧构造后有 6 个组合准确触发 draft buffer 断言，随后恢复新源码。完整 MTP 67 用例及相关 9 targets / 143 用例通过；该构造用例不执行模型 forward 或 graph replay，不能冒充端到端阶段实测。证据为 `default-interval-fix/revision3/gpu-ut/result.json`。

## 已核对案例：mega_fused 计数缺口要先核对依赖 API

来源：同一 session，2026-10-23 11:55:37（Asia/Shanghai），Turn 未核实，行 9103：「为啥现在没支持mega_fused的eplb监控，是kernel不支持还是链路上遗漏了？如果只是遗漏的话补一下」。raw 路径同上。

R-MIN-06、R-STA-10/11 已要求复用后端计数且保持真实接收口径；本轮读取正文。核对 x86_64 / CUDA 13 锁定的 DeepGEMM 2.8.0+122e18b wheel（SHA256 与该平台依赖锁一致），旧 mega_moe_fused API 在全部源码与二进制中均不存在。策略调用确实未消费 expert_load，但当前依赖连该策略所需的旧入口都没有，可用性检查会拒绝选择；不能从普通 mega 的 API 推断旧 fused 也接受 cumulative_local_expert_recv_stats。mega/mega_se 两条可用路径均已传递计数。

因此本轮不盲加参数，也不声称所有自定义历史 wheel 都缺少计数能力；这条意见是对已声明限制的调查，尚未证明代码漏接。已有规则足够，不新增防御或重复规则。版本、符号检查和调用链证据保存在 `default-interval-fix/revision3/mega-fused-audit.*`。


## 已核对案例：包级能力结论不能省略平台与版本

来源：session `01a15d3e-ab06-7732-ba3b-af0098e8b866`，2026-10-23 14:19:42（Asia/Shanghai），Turn 未核实，行 10198：「啥意思，解释清楚，是x86不行还是arm版本不行」。raw: `/home/baowending.bwd/.codex/sessions/2026/10/22/rollout-2026-10-22T17-19-12-01a15d3e-ab06-7732-ba3b-af0098e8b866_01a162e8-4734-7e01-810d-2803cb609841.jsonl`

上一轮审计 JSON 明确限定 x86 CUDA13，主 agent 最终答复和 PR 评论压缩为“当前锁定的 DeepGEMM”，丢失平台边界。R-TST-03 已要求结论与执行范围一致，R-REV-08 要求独立回读；本轮读取两张正文。属于总结时未落实已有规则，不虚构缺规则，也不把 ARM 当作未知私有包：仓库已有单独 ARM lockfile，应直接核查。

本次分别核对 x86_64 `2.8.0+122e18b.cu132` 与 aarch64 `2.8.1+057ca59`，SHA 均匹配对应 lock；两份包均无旧 mega_fused 四符号。准确结论是这两个锁定版本缺旧 API，不能外推 CPU 架构做不了融合或所有版本都缺。普通 mega API 的计数参数存在，也不证明所有调用参数兼容：ARM mega_se 的 shared_recipe 与签名不匹配是独立的既有问题。公开结论需保留“平台 + CUDA + 包版本 + 核查方式”，源码/包检查不写成 ARM GPU 实测。证据位于 `build_logs/eplb-ci-20261022/mega-fused-platform-audit/x86-audit.json` 和 `build_logs/mega-fused-platform-audit/arm-audit.*`。


## 已核对案例：确认停用后删除旧 mega_fused 策略

来源：session `01a15d3e-ab06-7732-ba3b-af0098e8b866`，2026-10-23 14:31:47（Asia/Shanghai），Turn 未核实，行 10407：「那你把这部分代码删一下吧，问了下mega_fused不支持了，这个单独一个commit；删完更新下pr的comment」。raw: `/home/baowending.bwd/.codex/sessions/2026/10/22/rollout-2026-10-22T17-19-12-01a15d3e-ab06-7732-ba3b-af0098e8b866_01a162e8-4734-7e01-810d-2803cb609841.jsonl`

这是在依赖审计后补充的停用确认与删除授权，不把此前未擅自删除历史策略归为漏检。已有 R-MIN-03（死代码一次删净）、R-OWN-13（调用链同步）与 R-DIF-02 足够；本轮读取正文，按用户要求独立提交，不 amend 已有指标实现。无需新增规则或退休开关兼容层。

处理范围包含两个旧实现文件、注册 import、选择器内旧开关与冲突判断、CP 同步白名单、两份 smoke 的旧环境变量。精确旧符号全仓零命中；当前 mega/mega_se 保留。两个 subagent 分别扫描/复核与执行 CPU 检查，主 agent 核对实际 diff 和结果。63 项现有 CED UT 与 14 项实际策略选择器 CPU 检查通过；后者仅隔离父包初始化/native quantizer 和 GPU 能力边界，不代表 GPU 前向验证。旧源码负对照的保留路径通过，删除契约按预期失败。证据目录：`/home/baowending.bwd/RTP-LLM/build_logs/mega-fused-removal-20261023/`。无新增规则卡，按既有规则补充本次判断记录。


## 已核对案例：区分已有 payload 与某一层的传参改动

来源：session `01a16309-49be-7181-970b-abfa99b86c2f`，2026-10-23，Turn 未核实。用户纠正“ExpertForwardPayload这个东西肯定不是我们新加啊”“一直都有的”，并追问“expert_load 在python里还是一个独立参数，你说的是哪个文件”。原话及核对记录：`/home/baowending.bwd/eplb-work/01a16309-49be-7181-970b-abfa99b86c2f/verify-only/user-feedback.md`。

`872d8f617a` 与新基线 `b51cb93f4f` 都已有 `ExpertForwardPayload`；变化只在 `FusedMoeExpertExecutor.execute` 这一层，负载上下文改从 payload 的字段取，`FusedMoe.forward`、MegaMoE 的 direct `forward` 仍保留独立参数。主 agent 先前已读取源码 diff，却把某一层变化概括成 Python 接口变化，造成歧义；这是表达范围不准确，不能声称新增结构或全部调用都改为 payload。

R-OWN-13、R-REV-04/08 已要求全调用链核对与 base 对照，规则和路由充分。本轮补明确文件/方法定位，记录执行与表达遗漏，不新增重复规则。代码仍沿用最新基线，只适配 runtime 的对应调用；不得为迎合表述删除合法的 direct forward 参数。

同轮用户进一步确认“eplb rearrange commit应该不感知这些吧，应该不会改到这部分”。此边界成立：最终 b942b117 相对最新 monitoring 基线 b51cb93，payload、execute 与负载传递方法的 AST 不变；rearrange 沿用这些契约，新增映射与权重迁移。已将本次 delta 与基线变化分开记录在上述 user-feedback.md，并由独立 Python 交叉审查核对。规则本身充分，本次只补执行复盘，不扩成接口重构。


## 已核对案例：启动异常要追到线程入口，V4.1 支持不能止于显式接口

来源：session `01a16309-49be-7181-970b-abfa99b86c2f`，2026-10-23，Turn 未核实。用户指出 EPLB initialize 的 Python 异常会从 detached grpc 初始化线程逸出，并明确“我们是需要支持v4.1的”。原文摘录与核对：`/home/baowending.bwd/eplb-work/01a16309-49be-7181-970b-abfa99b86c2f/verify-only/v41/source-excerpts.txt`、同目录 `user-feedback.md`。

此前把 NotImplementedError 描述成清楚的启动拒绝，没有追到 RtpLLMOp 的线程入口和 ready 等待。已有 R-MIN-02、R-OWN-12 和 R-REV-14 覆盖失败暴露、GIL 与并发回退；本轮读取正文后确认，旧判定没有具体要求检查线程异常返回通道。补充 R-REV-14 的判定及真实坏好例，不新增规则。独立审查又发现 HttpApiServer 借用 initRPCServer 栈参数，旧 Wait 间接延长其寿命；删线程前必须收敛该所有权。

V4.1 的支持范围按用户最新要求更新，保留私有 strategy 接入公共 EplbLayer；不把“不支持所以抛错”当最终交付。其 native shared group32、intermediate padding 和 gate-pack 路径分别核对，不能照抄 V4 模型接口后声称已支持。当前记录只确认源码链路与方案，实际修复、构造失败 UT、GPU migration/graph 与 smoke 以本轮最终证据为准，不预先记通过。

## 已核对案例：监控能力不足不得连带阻止推理

来源：session `01a16309-49be-7181-970b-abfa99b86c2f`，2026-10-23，Turn 与消息时间未核实。用户原话：“对于不支持的类型，为啥要直接CHECK呢，skip不好吗”。raw 原话摘录：`/home/baowending.bwd/eplb-work/01a16309-49be-7181-970b-abfa99b86c2f/verify-only/v41/source-excerpts.txt`。

本轮实际读取 R-MIN-01/02、R-OWN-01/02、R-STA-06、R-CFG-02/03/04、R-TST-01/02/03。既有冲突裁决第 16 条已区分正确性约束与可观测性退化；R-CFG-03 也要求默认启用时追查启动影响。无需新规则。此前把与基线一致的 monitor 行为保留并等待产品选择；本轮用户已明确要求 warn+skip，后续实现应直接执行，不能再以“不是本分支新增”或“已评审”当作不修复的理由。

本项目选择：不支持的设备/拓扑不分配 monitor，告警后推理继续；普通 dense 保留空窗口 1.0，仅省去 gather/reduction/D2H。不要据此把非法配置检查或动态权重迁移失败一并吞掉。测试需覆盖真实 balancer 路径，且证明 dense 无 collective；未执行前不声称通过。


## 已核对案例：模型 smoke 前核对架构对应的依赖能力

来源：session `01a16309-49be-7181-970b-abfa99b86c2f`，2026-10-23，Turn 与消息时间未核实。用户提出 V4.1 wheel 可能只适配 ARM，建议按同一 commit 补齐 x86、上传再测。raw 原话摘录：`/home/baowending.bwd/eplb-work/01a16309-49be-7181-970b-abfa99b86c2f/verify-only/v41/source-excerpts.txt`。

意见成立。仓库 `internal_source/docs/dsv41/main_migration.md` 已明确 ARM 验证范围与 x86 FlashMLA 缺口；ARM 锁为 DeepGEMM 057ca59、FlashMLA 2e5429f，当前 x86 实际 runfiles 仍为 122e18b、9241ae3。V4.1 生产 KV 格式为 528/288 字节，不能拿旧 x86 FlashMLA 或两项 MegaMoE UT 通过来证明完整模型依赖可用。首轮基线 smoke 更早出现 NVSHMEM device-state 999，后续 clone 报错；这条初始化问题须独立取证，不能把依赖升级预先称为它的修复。

本轮实际读取 R-TST-03/05 与既有“包级能力结论不能省略平台与版本”案例。已有规则已要求架构、版本、实测边界，属于 preflight 漏查迁移文档和实际 wheel 能力；未有证据证明各外部 reviewer 已读过迁移文档，不编造其漏读原因。不新增重复规则。后续模型跨架构验证须先核对对应 lock、实际 runfiles、wheel 源码版本和模型消费格式，再执行完整 smoke。

核对实际消费者后，修正范围收敛为更新 current FlashMLA、补齐 legacy namespace，并适配现有 DeepGEMM 122e18b 的 MQA 调用。按 ARM 的 057ca59 原 commit 构建的 x86 DeepGEMM 已上传，但不替换默认包：它缺少当前 x86 消费者使用的 SM120 扩展、MK alignment 控制和 shared_recipe，且需要更新的 libstdc++。现有 122e18b 的源码和真实 pybind 文档表明，显式指定 max_seqlen_k、clean_logits=False、logits_dtype=BF16 可选择所需的 compressed MQA 路径；CPU 接口测试不能代替 GPU 数值验证。相同版本的 rtp_kernel、FlashInfer、DeepEP/NVSHMEM 不因猜测全部重打。

三个 wheel 已上传并回读校验 SHA。current FlashMLA 的 Python 文件与 2e5429f 源码一致、ELF 架构和 CUDA cubin 已核验；原包没有完整 native 源码溯源清单，不能仅凭文件名声称 native commit 已被独立证明。legacy namespace 保留原 x86 9241ae3 native 字节，不冒充 ARM 的 92fd68b。依赖及 ABI 变更固定在公开仓库 4a772b1add / 内部仓库 ea393791fb；旧源码加同一兼容补丁、新源码关闭、新源码开启使用同一依赖集合测试，旧基线明确标为加过兼容补丁的 ef04cefe3d。

本版 35 个 Bazel UT 目标均通过；新增缓存格式、CPU ABI、真实 CUDA MQA 分别执行 2/5/4 个方法且无 skip，既有 CacheStore 集成另有 3 个方法 skip。V4 与 V4.1 六轮完整模型 smoke 均已执行，三方归档响应的稳定字段一致，开启 EPLB 后均有双角色、双 rank 主模型非零迁移及后续请求成功。两种模型各自的 5 项旧 golden 差异在三方相同，原 Bazel 失败状态保留，不能写成六个原 golden smoke 全绿。响应一致不证明未归档的中间张量逐位相同。V4.1 的 NONE 轮未及时采到 live maps，仅有实际 launcher/source/RTP 三库与 built native 来源证据；不能借另外两轮的 loaded 证据补成该轮已采样。证据见本任务 verify-only/v41/wheels/release-manifest.json、wheels/deepgemm/consumer-inventory.json、scope-x86-kernels.json、ut-run-round-6-root-audit.json，以及 aligned-113-plan 下的 v4-three-way-all-fields-comparison.json 和 v41-three-way-comparison.json。


## 已核对案例：严格参考移植与框架适配分别举证

来源：session `01a16309-49be-7181-970b-abfa99b86c2f`，2026-10-25，Turn 未核实。用户将 EPLB 要求明确为“严格按照deepinfer的实现”。原话与裁决记录：`/home/baowending.bwd/eplb-work/01a16309-49be-7181-970b-abfa99b86c2f/deepinfer-align-20261025/user-strict-reference-feedback.md`。

固定参考与旧实现的设备、层分组、通信和窗口语义均存在差异；旧UT通过不能支持“参考一致”。本轮属于要求进一步明确，不能自动判为此前需求已被违反。R-MIN-07、R-OWN-13、R-TST-01/02/03/04/05 与 R-DIF-02 已要求契约与证据对齐，无需新增照抄第三方的通用规则。后续评审必须核对固定参考契约矩阵、真实依赖版本及框架必须保留的差异。

可复现的参考 tie 局限与 inverse 副本顺序用固定 golden 保留；框架的借用计数、verify阶段、TP输入身份和混合DP阶段协调单独声明并验证。不能把CPU-only policy毫秒数冒充完整重排，也不能因换日志格式放宽全rank迁移的既有smoke校验。当前CPU证据不替代尚未执行的GPU、完整模型和性能测试。

同一会话随后明确要求最终 RTP 性能与 `/home/baowending.bwd/deepinfer-work/01a172fb-6e13-72a0-84e3-33a90f35d4bc/eplb-analysis-and-ut.md` 对齐（Turn 未核实）。这是一项本项目验收约束，不升级为所有移植都必须与参考跑分相同的通用规则。R-REV-11/12/13 与 R-TST-03 已覆盖计时边界、来源和实际验证，规则无缺口；后续提示必须显式给出参考的连续计数窗口、初始/期望映射、40+3 层完整字节布局，不能拿生产 target-only 40 层或旧版单层时间代替 full43。不同环境的直接对比和同环境 ABBA 分开呈现，首轮初始化与暖态分开，长尾不删除。实际运行及独立复核见该任务 `deepinfer-align-20261025/performance-results.md`；它是后续新增证据，不回写此前的“待测”记录为已通过。

## 已核对案例：首次 EPLB 延迟与启动预热

- 用户原话（2026-10-26，主会话 `01a16309-49be-7181-970b-abfa99b86c2f`，Turn 未核实）：「为啥第一次这么慢，分析一下，如果有什么东西需要warmup的话，在启动的时候warmup掉，runtime的1.675秒比较影响体验的」。公开证据：`/home/baowending.bwd/eplb-work/01a16309-49be-7181-970b-abfa99b86c2f/startup-warmup-20261026/user-feedback.md`。
- 问题定位：`dc29c119` 的 `RuntimeExpertBalancer` 把通信拓扑探测、对称显存分配和 rendezvous 留在首次 `rearrange()`。旧服务数据只有首轮总时间，没有细分初始化，不能用 cold-warm 差值直接归因。
- 归因：本次明确增加首轮请求体验要求；此前报告已分开 cold/warm，但没有完成冷阶段归因。R-REV-13 已覆盖阶段归因，不新增重复规则；无法仅据当前记录判断此前规则未读还是读后遗漏。
- 项目约束：测量后把可提前执行的一次性准备移到服务启动；预热不得改变权重、路由映射、窗口、update 序号或首轮触发时刻。核对临时 warmup executor 与正式 runtime 各自的生命周期，以及 STATS/暂停后在线开启。
- 本轮读取：R-MIN-01/04/05、R-OWN-05/11/15、R-STA-01/02/03、R-TST-01/03/04/05、R-REV-11/12/13。验证应含阶段诊断、真实跨卡状态/权重检查及同机前后首请求对照，不能仅凭 constructor 单测宣布首轮性能已解决。

- 后续实测证据：公开库 `9576870171` / 父库 `8223bafefe`，正式同机八卡首轮从 1283.07ms 降至 177.74ms；8 个 runtime 均在 ready 前准备，live 初始化为 0。20 请求输出 token IDs 一致，37 CPU、7 双卡、7 八卡场景通过。真实服务最慢 rank 的 initialize_shuffle 为 1054.29ms；独立进程 scatter_add_ 的约1.5s仅作额外冷路径证据，不冒充服务阶段分解。完整边界见 `/home/baowending.bwd/eplb-work/01a16309-49be-7181-970b-abfa99b86c2f/startup-warmup-20261026/startup-warmup-results.md`。

## 项目约束：融合策略直接替换，不增加开关

来源：主会话 `01a16309-49be-7181-970b-abfa99b86c2f`，2026-10-26，Turn 未核实。用户原话：“注意这个功能是直接替换，不要加开关/环境变量”。公开记录：`/home/baowending.bwd/eplb-work/01a16309-49be-7181-970b-abfa99b86c2f/policy-fused-20261026/user-feedback.md`。

这是本轮明确需求，优先于所参考集成文档的可选环境开关。当前代码尚未加入该开关，不属于已经发生的漏检。R-CFG-04、R-MIN-07 与 R-TST-04 已覆盖输入能力选择、最小实现和性能替换对照，规则无缺口，不新增重复规则。保留 CPU/ROCm、非连续、其他 dtype 和窗口的既有算法是接口兼容；不得用异常捕获把融合路径故障隐藏为自动降级。后续 reviewer 必须核对公共入口是否真实命中融合路径、三输出是否与当前 RTP ref 一致，以及运行环境变量中是否引入新能力开关。


## 已核对案例：性能替换须覆盖当前生产默认输入

来源：主会话 `01a16309-49be-7181-970b-abfa99b86c2f`，2026-10-26，Turn 未核实。用户指出生产只有稳定连续的 `[step,L,Logical_Expert]` 计数，质疑兼容分发是否使优化无法用于生产。原话及源码判断：`/home/baowending.bwd/eplb-work/01a16309-49be-7181-970b-abfa99b86c2f/policy-fused-20261026/user-feedback-window.md`。

意见成立。d44228fd 真实 runtime 分配连续 int32；DeepInfer 原型的生产窗口4与RTP默认100不同，入口 S∈{1,2,4} 使默认配置继续旧慢路径。此前将 float64/非连续兼容与生产可用性混述，且未将参考假设对照当前配置消费者。R-MIN-07、R-OWN-13、R-CFG-03/04、R-TST-03/04 已有充分要求，属于主agent执行遗漏；本轮DeepSeek已指出该缺口，不能声称外部审查漏检。

当前用户约束优先于原型“范围不能放宽”的建议：补真实窗口归约语义及默认100的三输出严格reference对照，再验证实际生产命中融合；不能简单扩大分发、修改默认值或增加开关。旧4步的绿灯不外推到新版本。保留其他设备兼容与默认生产加速分别核对，后续review提示显式包含当前默认配置和唯一生产调用点。规则正文与路由充分，本轮只补复盘，不增加重复规则。

同轮后续用户明确生产 prefill=100、decode=1000；随后调整分工为“先集成，按照现在能跑的把整个链路跑通；kernel我让另外一个subagent改”。因此本轮停止扩窗实现、保留任务目录诊断原型供交接，以现有支持窗口完成链路测试；这不是撤销生产窗口要求，也不代表100/1000已融合验收。按最新分工描述范围，不继续修改另一个agent负责的kernel。


## 已核对案例：xgrammar 超时告警在状态转换处记录

来源：session `01a1679e-1e67-7672-8d91-6e7bdcd8c3be`，2026-10-26 16:25:20（Asia/Shanghai），Turn 未核实，行 757。用户原话：「updateLogitProcessorStatus里没必要logging吧，这个会导致每一轮都遍历+logging的，直接放在xgrammarUpdateTimedOut里？」raw: `/home/baowending.bwd/.codex/sessions/2026/10/26/rollout-2026-10-26T14-50-04-01a1679e-1e67-7672-8d91-6e7bdcd8c3be_01a176f9-2ed3-7ee1-8116-8e3427907aaa.jsonl`。

意见部分成立。`0ac1866b5d` 的 WARNING 已只在 false→true 时打印，但每轮 update 在 grammar 内部判定之外，再做类型检查和两次加锁读取。processor 遍历本身承担真实更新，不能删除。直接把日志挪到 `xgrammarUpdateTimedOut()` 会在 sticky timeout 后每次读取重复打印，且它唯一生产调用受 `aux_info` 开关控制，关闭时会漏警告。

本轮实际读取 R-MIN-10、R-OWN-02/04/05、R-STA-01/12、R-TST-01/02/03 与 R-REV-01–05。既有规则已要求失败产生处单次记录、单一状态所有者和锁外日志，规则与路由充分；主 agent 上轮漏查重复读取成本，无法确认旧审查是否完整读取 R-MIN-10 正文，不编造其漏读原因。本次只补复盘案例，不新增去重规则或成员。

修正将既有 `streamLogTag()` 在构造时按值经 factory 传给 grammar，WARNING 与首次超时 QPS 同在锁外分支。stream 更新循环只推进状态，getter 只读；不复制身份回退逻辑，不新增 timeout/已打印镜像状态。独立 subagent 已按实际调用链复核构造期标识、字符串生命周期、单次分支与 aux_info 关闭路径。编译、运行记录及最终版本保存在 `/home/baowending.bwd/xgrammar-work/01a1679e-1e67-7672-8d91-6e7bdcd8c3be/warning-feedback-20261026/`，不能把源码审查写成日志运行测试通过。


## 已核对案例：collector 按需构造与日志字符串移动

来源：session `01a1679e-1e67-7672-8d91-6e7bdcd8c3be`，2026-10-26 16:51:12（Asia/Shanghai），Turn 未核实，行 956。用户原话：「collector不用提前创建的；在update_timed_out_的分支里做就行」「createLogitsProcessors参数调用streamLogTag()，确认下这里是不是会做std::move的优化，否则就是要重新构造一次字符串」。raw: `/home/baowending.bwd/.codex/sessions/2026/10/26/rollout-2026-10-26T14-50-04-01a1679e-1e67-7672-8d91-6e7bdcd8c3be_01a176f9-2ed3-7ee1-8116-8e3427907aaa.jsonl`。

第 1 点采用：`607d5abd28` 的 collector 被提前创建并用作锁内外的状态快照，虽不导致重复上报，但扩大了使用范围。本轮用 unique_lock 在持锁时直接判断首次超时，在分支内先 unlock；仅当 reporter 存在时构造 collector。正常路径直接初始化 error，去掉预先赋 OkStatus，不另加状态镜像。R-STA-12 与最小实现原则已足够；上轮主 agent 已读相关正文但只核对了单次上报、未收敛局部对象生命周期，本次是简化遗漏，不能宣称已有可测性能损失。只追加案例，不新增重复规则。

第 2 点核实无需改动：项目使用 C++17，streamLogTag() 的 prvalue 直接初始化 factory 的按值参数；函数内 return tag 可 NRVO，否则隐式移动。factory 与 grammar 构造函数已各用 std::move，目标 const 成员不阻止从非 const 源初始化。存在参数/成员的移动构造，不代表重新拼接或深拷贝字符串；短字符串实现可复制内联字节。不能给 prvalue 机械补 std::move，也不能把源码核对写成分配次数实测。

本轮读取 R-OWN-02/04/05/13、R-MIN-10、R-STA-07/12、R-REV-01–05。独立 reviewer 另指出初稿 const error 会失去返回时的隐式移动，主 agent 已改回 auto error，保留直接初始化。最终源码、两次 CPU 用例记录、裁决与复核保存在 `/home/baowending.bwd/xgrammar-work/01a1679e-1e67-7672-8d91-6e7bdcd8c3be/collector-feedback-20261026/`；实际执行结果以该目录 validation 为准。


## 已核对案例：grammar 派生覆盖与 MTP 接受长度口径

来源：session `01a1679e-1e67-7672-8d91-6e7bdcd8c3be`，2026-10-26，Turn 未核实。用户问「有没有继承他的，但是实际上把你改的函数重载了，导致走不进去的呢」，随后询问「最终接受长度应该是投机采样接受长度和xgrammar最大长度取min的，这块逻辑现在是咋样」。raw: `/home/baowending.bwd/.codex/sessions/2026/10/26/rollout-2026-10-26T14-50-04-01a1679e-1e67-7672-8d91-6e7bdcd8c3be_01a176f9-2ed3-7ee1-8116-8e3427907aaa.jsonl`，首问行 1136，全部原话及定位保存在 `dispatch-audit-20261026/user-feedback.json`。

固定 `0dde84447d`：GrammarLogitsProcessor 已是 final，factory 直接构造该类型；BaseLogitsProcessor::updateStatus 为纯虚函数，normal/update 与 MTP/specUpdate 均到共同虚调用。Tree/Recommendation/MultiSeq 等是 Base 的其他派生类，不是 Grammar 的子类。公开和内部源码未发现用户担心的派生覆盖遗漏，无需为此修改代码。

MTP 的 grammar cap 表示合法 draft 前缀长度，sampler accept_len 还包括最后一个 target 纠正/bonus token。实际代码 `min(accept_len, cap + 1)` 与草稿口径下取 min 一致；在 cap 截断处用已受 grammar mask 约束的 target token 替换非法 draft，不能只删 +1 或单截长度。超时后 cap=P 且 mask 全放行，后续不再限制。prepareSpeculative 临时 accept/rollback 与真正提交 updateStatus 是两阶段：当前 10ms 只检测后者，不能因提交路径覆盖便声称预验证也有超时检测。

本轮读取 R-OWN-13/15、R-REV-02/04/05、R-TST-03；已有规则要求追真实调用链并区分阶段口径，规则充分。用户提出的是覆盖核查问题，假设未成立，不伪造已确认漏检或补重复规则。本次仅补事实与边界案例，源码静态核查不写成新 GPU 测试通过。证据目录：`/home/baowending.bwd/xgrammar-work/01a1679e-1e67-7672-8d91-6e7bdcd8c3be/dispatch-audit-20261026/`。


## 已核对案例：解释 timeout 到 MTP GPU cap 要补齐生产者与对象身份

来源：session `01a1679e-1e67-7672-8d91-6e7bdcd8c3be`，2026-10-26，Turn 未核实。用户追问「verify_result.spec_cap_gpu会被影响到吗？链路上怎么传递的给我仔细讲一下」，以及「fork出多个processor给每个draft位置用，fork的时候有没有把timeout flag拷贝」。raw: `/home/baowending.bwd/.codex/sessions/2026/10/26/rollout-2026-10-26T14-50-04-01a1679e-1e67-7672-8d91-6e7bdcd8c3be_01a176f9-2ed3-7ee1-8116-8e3427907aaa.jsonl`；精确原话与行号存于 `cap-fork-flow-20261026/user-feedback.json`。

固定 `0dde84447d`：上一条答复给出了 cap 公式，却省略本 PR 还修改了 prepareSpeculative 的超时分支，没把返回值到 GPU tensor 的生产者/消费者链讲完整。属于解释不充分，不能据用户疑问虚构实现缺传递。R-OWN-13/15 与 R-REV-02/05、R-TST-03 已覆盖实际调用链和验证边界；本轮读取并应用，无需新增重复规则。

实际链为：updateStatus 设置 bool → 下一轮同一 processor 的 prepareSpeculative 返回 P 并全 allow mask → runner 每轮初始化 cap=P，合并各 processor 返回值 → copy_ 到 GPU → result.spec_cap_gpu → min(accept_len,cap+1)。其他 processor 仍可产生更小 cap。普通 decode 的 process 早退本身不会修改这个 GPU tensor。async 在生成下一轮 spec artifact 前等待前轮 CPU bookkeeping，ready_event 约束 H2D 消费顺序；当轮已经完成的采样不会被超时 flag 回写。

当前 MTP/DSpARK 取 stream 持有的 shared_ptr 放进 task.active，每个 processor 一次接收整组 draft。各位置是 P+1 行 mask，同一 matcher 临时 accept 后 rollback；不是每位置复制 processor。flag 仍在同一个对象里，无需 fork 拷贝。不可用 final 本身证明不能复制，判断依据是实际 shared_ptr 传递与调用链；matcher adapter 的复制/移动构造另已删除。历史其他版本是否 fork 未核对，不猜用户记忆来源。

本轮只读源码，无新测试、无代码改动。两位独立 subagent 分别复核 cap 生命周期/异步时序和对象身份/位置循环；证据保存在 `/home/baowending.bwd/xgrammar-work/01a1679e-1e67-7672-8d91-6e7bdcd8c3be/cap-fork-flow-20261026/`。后续说明须同时交代何时产生新结果、传递的实际值及是否共享对象，不能只列末端公式。


## 项目约束：大窗口允许近同分布局差异，但归因与跨卡验证必须独立

来源：主会话 `01a16309-49be-7181-970b-abfa99b86c2f`，2026-10-26，Turn 未核实。用户原话：“接受近同分布局差异，但须验证一致性归因、跨卡稳定性和端到端回归”。原文定位及本轮裁决：`/home/baowending.bwd/eplb-work/01a16309-49be-7181-970b-abfa99b86c2f/policy-larges-20261026/user-feedback.md`。

此要求覆盖本项目此前对大窗口的严格布局一致要求；S1/2/4继续严格，其他窗口需逐轮近同分归因、真实跨设备稳定性和旧源码端到端对照。原型同卡多进程/顺序调用不等于跨卡；只证明Torch两个候选近同分不能证明融合实现所选第三个候选合理。R-TST-01/03/04/05和R-REV-13已有足够约束，当前主agent已读取相关正文并补独立oracle与负向用例；不新增重复规则，不把新的用户许可追认为旧测试已覆盖。GPU与服务实测结果以当前任务归档为准。

## 已核对案例：EPLB 融合参数的 JIT 复用与退役接口生成文档

来源：session `01a16309-49be-7181-970b-abfa99b86c2f`，2026-10-28，Turn 未核实。用户要求确认新增 Triton 参数不会随 shape 反复 JIT，并指定一个本地 subagent 检查 kernel 与 `EPLB_CONTROL_STEP` 删除，不调用 Claude。

固定公共 HEAD `e4f5cac4525ebe2e1cd09a208d22c501889a6ae1` 中，`M`、`ep_rank` 已设 `do_not_specialize`；映射表和计数是运行时指针，rearrange 原地 `copy_` 不改变容量。补充真实 GPU 回归：预热原有 `BLOCK_M=2/4/8` 后，22 种长度、7 个 rank、hash/nonhash 和 Mega/MegaSE 共 616 组合禁止进入 `_do_compile`，全部通过。结论限于固定模型配置和三档预热；不将 dtype、topk、映射容量等静态配置变化说成永不编译。此前数值等价 UT 没有检查编译入口，属于验证维度不足；R-TST-01/02/03 已覆盖，不新增重复规则。

本地 reviewer 发现 `docs/build` 有 18 个受版本管理且由 `docs/deploy.py` 发布的旧 CLI/API 生成文件。活跃代码删除完整，但交付文档没有清干净。R-MIN-03 的删除范围适用，先用 `git ls-files` 和发布脚本判断归属，不能仅因目录被 ignore 就排除。此前是否读过该规则无法确认。本轮定点删除对应段落、notebook cell、gettext 项和搜索索引；第一次补丁误删相邻 `Update-Log-Level` section，主 agent 与 reviewer 均发现，恢复后逐 section 核对。修正版不再删除相邻内容。

本轮实际读取 R-MIN-03/06/07、R-TST-01/02/03/05，reviewer 另记录所有权、状态、配置正文。只补反馈案例，不改变规则数。证据目录：`/home/baowending.bwd/eplb-work/01a16309-49be-7181-970b-abfa99b86c2f/prefill-control-20261028/test-env/`，含 `jit-reuse-r1.log`、`jit-cache-review.patch`、`control-generated-docs-review-r2.patch` 与 `local-review-result.txt`；修正版文档 patch SHA256 为 `f5bb78f59709a1e125030ad0f54535e4d2492b5aeebe1f9a871fc15bde1d2a3f`。


## 已核对案例：思考开关、请求元数据与异步验证范围

来源：2026-11-01 当前会话用户提供 Claude 的十条 review，并明确「普通解码ut能过就行，主要是mtp+异步的情况」「如果合理的话修复」。Turn 未核实。基线 c79c659d69，迁移分支 codex/xgrammar-dsv41-20261101。

上一轮虽检查了 Python 服务开关，却未追到 C++ 工厂，导致关闭开关仍创建 ThinkingState；超时改成请求失败后，也漏跑了仍断言继续生成的 GenerateStreamTest。R-CFG-03、R-OWN-13、R-TST-02 已覆盖这些要求，规则充分，遗漏发生在执行范围。本轮增加默认 false 的 RPC opt-in，缺省字段保留旧前端思考信封语义；正常和 MTP 超时测试验证 614、没有成功输出及迟到更新不能继续推进。

DISABLED 标签清理还必须检查准备函数之后的写入：DashSC 会回填 runtime.eos_tokens，phase-2 会继承第一阶段标签。仅测 GenerateConfig 清空列表不足以证明发送给后端的配置正确；正式 servicer 测试先暴露这两处，再修复。单 token 校验加入后，旧 Qwen 夹具和假 tokenizer 也要明确提供原生边界，不能放松生产校验迁就夹具。

DSpark 配置本身不能证明异步执行。首轮真实服务日志是 useStreamAsync=0；新 smoke 显式设置 RTP_LLM_STREAM_ASYNC=1，并检查四个 rank 的分支日志，同时要求实际 speculative rounds 和 accepted tokens。高水位回归新增两个 Earley 历史的精确增量断言，保留回滚峰值测试。独立 reviewer 关于 std::vector 支持自身区间 insert 的理由不成立，已对照标准前置条件修正测试 oracle；RemapVector 自身已测试的保护保留。ErrorCode 无关对齐来自固定 clang-format 19.1.1，不将其列为运行时缺陷。

修复至 2f338ff37c；执行结果以 /tmp/xgrammar-dsv41-review-verification-20261101/ 和 /tmp/xgrammar-dsv41-smoke-evidence-20261101/ 为准，不能把首轮非异步 smoke 或此前版本的 UT 追认为最终版本通过。本次只补漏检案例，不新增重复规则。

本轮最终验证：14 个 UT 目标通过，731 项通过，保留原有 1 个 skip 和 1 个 DISABLED；DSV4.1 DSpark 显式异步 smoke 24/24 通过，四 rank 均 useStreamAsync=1，共 215 个 draft rounds、412 个接受 draft token。ADAPTIVE 四例均选 DIRECT，思考路径由 ENABLED 场景覆盖。服务进程、GPU 锁和本轮 Engram 共享表已清理。


同日完整 review 补充了 V4.1 recipe 的旧信封断言、smoke suite 入口和历史上限用例的弱断言。前轮 14 个目标没有覆盖 `v41_recipe_endpoint_test`；不应以这些目标通过推断所有调用方夹具已同步。此次把 recipe 的假 tokenizer 改为原子思考 marker，检查服务 opt-in、DISABLED 空元数据、独立 final schema 及 closing suffix，保留原预算与 stop 契约。上限回归改为同一预算下的短 draft 成功对照与长 draft 回滚后失败，二者最终提交相同 token，避免 `initial+1` 把当前占用超限也误认为峰值计费正确。R-OWN-13、R-TST-01/02/03 已覆盖调用方机械同步和独立行为验证，属于执行遗漏；本轮只补案例，不新增重复规则。后续结果存于 `/tmp/xgrammar-dsv41-review-verification-20261101/followup/`，与前轮实际 smoke 的提交分别记录。

补充修复提交 1309bf7465：grammar 38 项、recipe 21 项全部通过，测试源码散列与提交一致；在 x86_64 CUDA13 环境执行，未声称 ARM lane 已实际运行。四个新 smoke 明确标注 manual-only：CI 中已有 DSV4.1 分离 P/D fixture，但新目标的精确 3FS 路径和 TP4/EP4 配置在 CI worker 上仍未验证；不能拿其他分支 V4 用例成功或本机 24/24 手跑当自动覆盖。五个被点名 C++ 文件的格式差异均可由固定 clang-format 19.1.1 重现，保留 hook 要求的格式。此次没有生产代码变化，不重跑已通过的整模型 smoke；该实测仍绑定 2f338ff37c。


## 用户调整契约：连续三次超时后只禁用请求的 grammar

来源：2026-11-01 当前会话，用户在设计问答中明确选择「第三次禁用 grammar，继续无约束生成」，随后要求「好的，继续修改吧」。该决定覆盖同会话上一轮的超时返回 614 方案；这次属于用户调整行为契约，不将此前按旧契约完成的验证追认为漏检。

计数归属于请求的 GrammarLogitsProcessor，只统计非空 committed update。及时成功一次清零，空更新不计数也不清零，MTP 一批接受多个 token 只算一次；draft 临时 accept/rollback 不计数。第三次慢更新成功提交后，停止推进 matcher，保留 committedOutputLen 推进和流一致性检查；新的 speculative mask 全部 P+1 行放行，grammar 自身 cap 恢复 P，独立 ThinkMode 和其他 processor 继续生效。已在上传的 mask 不原地修改。parser 拒绝和 history 上限错误先于超时判断，仍失败；aux 标记及已有 timeout QPS 从第三次才生效，QPS 仅记一次。

R-OWN、状态契约和 R-TST 现有规则已覆盖，不新增规则。确定性退化、计数清零、混批隔离和异步 mask 生命周期由 UT 验证；DSV4.1 DSpark+async smoke 只验证正常路径回归，不声称整模型 smoke 注入了超时。当前实现、源码散列和各轮结果记录在 `/tmp/xgrammar-three-timeout-20261101/`，整模型证据记录在 `/tmp/xgrammar-dsv41-three-timeout-smoke-20261101/`；结果以完成后的验证文件为准。


本次提交 `1954ad5d71` 的 7 个 UT 目标共 287 项通过，保留原有 1 项 DISABLED。首轮新增 MTP 流提交用例发生段错误：测试的空 ResourceContext 没有 cache manager，旧失败路径提前返回，新成功路径进入多 token 缓存处理后解引用该空指针。测试夹具改为已初始化的真实最小 MHA 缓存上下文，仍提交每批两个 token，重跑 GenerateStream 57/57 通过；未修改生产代码来迁就夹具。最终提交树和 UT 源码散列一致，完整结果含失败首轮与修复后重跑，见 `/tmp/xgrammar-three-timeout-20261101/ut-results.json`。

同一提交 `1954ad5d71` 的 DSV4.1 Flash DSpark＋异步 smoke 24/24 通过，四 rank 均 useStreamAsync=1，共 215 个 draft rounds、412 个接受 token，未观察到超时降级标记。ADAPTIVE 四例均选 DIRECT，思考路径由 ENABLED 覆盖；不扩大为 ADAPTIVE THINK 实测结论。测试进程、监听端口、GPU 锁和本轮两份 Engram 表均已清理，JIT 缓存保留。最终结果：`/tmp/xgrammar-three-timeout-20261101/final-results.json`。


同日用户继续指出「prepareSpeculative 和 updateStatus 都和 matcher 状态有关系」「配置时间短＋token 数多」时整段计时可能误触发。固定 `1954ad5d71` 回查：现有 steady_clock 仅包住锁内 acceptCommittedLocked 整批循环，prepare 的逐位置 fillBitmask、临时 accept 和 rollback 均未计时；思考 token 又不一定调用 matcher。连续三次策略只解决偶发采样，并未解决固定整批预算随工作量增长的问题。上一轮 UT 检查整批只计一次，但没有验证不同 token 数下单步预算公平性；源码能证明口径差异，不能替代真实耗时测量。R-STA-11 和 R-TST-01/03 已覆盖粒度及验证范围，属于此前设计评估范围不足，不新增重复规则。本轮只核查并讨论单次 matcher 操作计时与阶段独立统计，不改生产语义；证据为 `/tmp/xgrammar-three-timeout-20261101/timer-scope-review.json`。


## 用户纠正计时范围：MTP verify 与 committed update 独立计数

来源：2026-11-01 当前会话，Turn 未核实。用户明确说明 timeout「主要是为了规避单次 xgrammar 内部状态推进/验证时间过长」「整批共用，这个我们可以先不管，因为 timeout 参数可以调整」「timeout 应该有两个 flag，分别计数，避免互相影响，logging 时候也清楚一点，只是到 stream 层还是和原来一样感知就行」，随后收敛范围为「可以只管异步+mtp的链路，其他先不管」。

这覆盖上一段提出的逐 token 预算建议；此前把 token 数量公平性当成主要设计目标，偏离了用户希望覆盖慢状态推进和慢验证的需求。当前采用固定整次调用预算，prepareSpeculative 包括逐位置 mask、临时 accept 和 rollback；updateStatus 包括整批 committed accept。各阶段独立连续计数，快的另一阶段不能清零；任一达到三次才永久禁用请求 grammar。stream 继续读原有合并标记，日志写明阶段、预算、耗时和 token 数。普通 decode 不增加 mask 计时或重构。

R-MIN-07、R-STA-11、R-TST-01/02/03 已有最小范围、统计口径与验证边界要求，本轮重新读取并应用，无需新增规则。超时在同步调用完成后判定，降级前先恢复 speculative 状态并保留真实错误优先级；不能宣称能打断尚未返回的 xgrammar 调用。计数独立性、第三次即时放行、错误优先、stream aux 及 pending mask 的生命周期由确定性 UT 检查。源码快照、独立 review、测试结果分别保存在 `/tmp/xgrammar-dual-timeout-20261101/` 和 `/tmp/xgrammar-dual-timeout-smoke-20261101/`，未完成的实测不提前标通过。

本轮提交 `d450754129` 的 7 个 UT 目标实际执行并通过 293 项，保留原有 1 项 DISABLED；46 项 Grammar、58 项 GenerateStream 和 9 项 SpecLogitsVerifyRunner 包含本轮确定性超时回归。测试源码散列与提交树 `babb6b7a8659a34d54a09f5e040de2014e1393ca` 一致，pre-commit 通过；模型 smoke 仍需单独完成。

同一提交 `d450754129` 的 DSV4.1 Flash DSpark＋异步 smoke 24/24 通过，四 rank 均开启异步，215 个 draft rounds、412 个接受 token；没有 timeout 标志。ADAPTIVE 实际为 4 DIRECT、0 THINK，THINK 由 ENABLED 场景覆盖。此次 smoke 未注入超时，独立连续计数与 stream OR 的验证来自 UT。进程、监听端口、GPU 锁和本轮两份 Engram 表已清理，JIT 保留；汇总 `/tmp/xgrammar-dual-timeout-20261101/final-results.json`。启动监控曾因 Bazel 软链漂移误显示 queued，改用当前 output-base 绝对路径后恢复；未重启测试，也未修改已验证的仓库源码。


2026-11-01 同一会话用户进一步明确：「这个功能不要用 smoke 来保证，ut 保证就行，ut 覆盖全面」，并要求按文件解释修改目的。本约束覆盖此前要求继续跑模型 smoke 的验证计划；后续双路连续超时功能以 UT 验收，不把正常路径 smoke 计作超时、恢复或异步生命周期的覆盖。本轮回查两个提交 `1954ad5d71`、`d450754129`，范围均为同一组 8 个文件：2 个生产实现、3 个测试、3 个注释/help 同步。确定性 UT 已覆盖独立连续计数、单路清零、空更新、多 token 批次、降级永久性、mask/cap、错误优先、指标一次性、stream aux/长度/结束边界和 pending H2D；已有通过结果仍绑定原提交，不宣称本轮重跑。R-TST-01/02/03 已覆盖验证按契约与用户范围执行，无需新增重复规则。


2026-11-01 同一会话用户指出「是不是有什么 thinkmode 和 grammar 隔离呢，那部分代码呢」。此前只列连续超时两个提交的 8 个文件，遗漏早先 thinking/grammar 分离，说明范围不完整。后续按用户要判断的完整功能说明文件职责，并标明所用基线；ThinkingState、两个 processor、factory、Python 编译与 RPC 传输均属于分离链路。两边各持状态机实例，只有答案 token 推进 xgrammar，不能说 grammar 完全不感知 thinking。现有范围与状态契约规则已覆盖，无需新增规则。按用户要求删除先前 4 个模型 smoke target、共用脚本和两份配置，提交 f0c46a1f42；BUILD 恢复到基线，残留引用、Bazel query 和 pre-commit 检查通过。生产与 UT 源码未改，此次没有重跑 UT 或 smoke；历史测试结果仍绑定原提交。证据 /tmp/xgrammar-remove-smoke-20261101/final-results.json。


2026-11-01，session `01a1954f-e9d7-7562-b5d4-1fc5328d5e09`：用户要求将独立分支应用到当前 workspace 后，agent 错把补丁叠入已有 EPLB 分支。用户指出「没看到啊，现在这个workspace分支是codex/eplb-cpp-step-20261028, 还有一堆diff不知道是什么」。已读 R-DIF-01、R-WRK-03，规则充分，属于执行时误判用户意图。修正与原话定位见 `/tmp/xgrammar-workspace-switch-20261101-qirh2imt/feedback.json`；原 EPLB 现场移到备份 worktree，当前目录切到已测提交 `2f71679cda`，源码树一致且工作区干净。不新增规则。


2026-11-01，同一会话用户要求简化同锁内的 timeout 判断、调整 `timedOutLocked` 命名并合并提交。复核、原话定位、规则归因和生效边界记录：`/tmp/xgrammar-timeout-cleanup-20261101-gx3n7i1q/feedback.json`。后置检查要判断本次计数变化，不能因入口检查过就整个删除；可去掉对另一阶段状态的重复读取。命名属于本轮明确偏好，不推广为禁止 `Locked` 后缀的通用规则。

用户随后明确选择「本轮保留结果，下轮开始禁用」，并强调「我们的目的是干掉那些超长更新状态的xgrammar行为，不是改结果」。原话在同一 feedback 文件的 followup_sources 中，可回查 session jsonl 第 7475 行及后续消息。此前第三次慢 verify 返回前覆盖 mask/cap，会改变已经算完的当轮结果；现改为原样返回，下一次调用才跳过 matcher，删除显式 unlock。R-MIN-01、R-TST-01/02 已覆盖最小实现和行为边界，属于对当前需求的误读，不新增通用规则；独立测试比较正常调用与第三次慢调用的完整 mask/cap，覆盖 cap=0/1/P、bonus 行和实际未完成 H2D。最终运行结果以同目录 ut-results.json 和 source.json 绑定的提交为准。

2026-11-02，同一 session，Turn 未核实，当前用户消息纠正：「我们要的是统计的是gpu上的等待时间，并且propose下一轮应该是要等待新的数据过来的吧？不应该只有采样前一个同步」。此前图画的是 CPU worker 等待，且没有完整表达跨轮输入依赖；R-STA-11 已要求区分统计对象，本轮重读后确认属于需求口径误判，不新增规则。固定 `ba26ddf1dd86c02bcee3cc6eee966ca59e4ae7a6` 回查：下一轮 DSpARK propose 消费接受 token、位置和已提交 KV；轮首 bookkeeping join、scheduler 的 KV reservation join、target prepare、采样前 bookkeeping/spec verify、draft prepare 都可能使消费方 GPU stream 无法继续。device state 可用且允许 drop broad sync 时，可先运行下一轮 propose，host matcher 的依赖后移，不能画成无条件等待整个 bookkeeping，也不能忽略跨轮数据依赖。设计改为消费方 CUDA stream 的依赖停顿，排除已被前序 GPU 工作覆盖的 CPU 等待；轮间观测要覆盖 scheduler，不能只包 decodeStep 内部 sync。图仅为依赖顺序示意，未实测耗时、未修改生产代码；新图为 thread visualization 目录下 `mtp-gpu-wait-boundaries.html`，取代旧 CPU-worker-wait 图的监控口径。此段统计口径随后被下述明确澄清覆盖。

2026-11-02，当前会话用户要求「先把这几个线程之间的关系理清楚，然后只关心gpu worker在等待的耗时，最后再出方案」，在区分主线程与 CUDA stream 的问题中明确选择「主线程 normal_engine_loop 的阻塞时间」（来源：本轮用户可见原话及异步问答回复；Turn 未核实）。此前未先确认 GPU worker 的具体执行对象，就持续用 CUDA event 和设备空档解释，是需求理解与线程归属核对不足。已读 R-STA-11、R-STA-07、R-OWN-08，规则足够，不新立卡。

同一源码基线确认：bookkeeping 的前置 sync 在主线程的 launch helper 中，真正的 verify callback 才在独立 worker 中；AsyncRunner 的 launch/sync 都可能在主线程等待 task_done，而 worker 的 task_done 只证明回调返回并已 record CUDA event，不代表设备执行完成。新方案统计主线程抢锁、cv_done 等待及唤醒的 wall time，不扣除 GPU 并行计算，不累计后台 worker 自身耗时；轮首 host 同步沿用用户要求暂不纳入。候选方案及源码锚点保存在 `/tmp/mtp-sampling-wait-monitor-20261102-0y25q0d7/monitor-plan.json`，原 CUDA event 方案留作 superseded 记录。此轮只做方案，没有新增生产计时器或执行新 UT；此前 251 个用例通过仅对应旧指标删除。

2026-11-02，同一会话用户继续纠正「不是就2个计数吗？为啥有5种原因」，随后授权实现。最终范围只含 normal_engine_loop 在采样前等待上一轮 bookkeeping、本轮 spec verify 的两个整批耗时；其余 wait 不加入本次监控。已有 R-MIN-07 与 R-STA-11 足以约束，属于明确统计对象后仍扩大范围的执行误判，不新增规则。实现沿用现有同步点与指标组，不改 AsyncRunner 接口；最终设计记录 `/tmp/mtp-main-thread-wait-20261102-695vyuhe/monitor-plan.json`。来源为当前会话用户可见原话，Turn 未核实。


## 用户明确移除改名前的字段名

来源：2026-11-03，session `01a1a052-cad4-7752-8248-211e25971f3b`，当前用户消息「改名，然后shutdown_worker_grpc_addrs代码里不该搜的到」，Turn 未核实。

全 rank profiler 复用停服协调的 world 地址列表后，生产字段已泛化为 world_worker_grpc_addrs，但测试文件与 Bazel target 仍叫 shutdown_worker_addrs_test，Python 还保留了旧字段别名及别名专用 UT。用户明确要求只保留新名；本轮同步测试文件和 target、移除别名及专用断言，保留全 rank 地址、排序与 pickle 测试，tuple 位置不变。R-OWN-08/13、R-MIN-03 和 R-TST-02 已覆盖职责命名、全链路同步与契约测试；此前是命名收尾遗漏，以及在未确认旧名调用方的情况下预留兼容接口，不新增通用规则。用户本轮要求只适用于该字段，不能推广为所有接口改名都删除兼容性。


## all-rank profiler：本地排空与共同 step 是两个验收条件

来源：2026-11-03，session `01a1a052-cad4-7752-8248-211e25971f3b`，当前用户要求「async decode 时候能够采集每个 rank 从同一个 step 出发的 timeline，不会错位（在 2s 能够排空 gpu worker 的前提下）」「只有在 rpc 通知的情况下会有 2s 延迟」，后补充「rpc 失败的情况下，timeline 虽然可能错位或者缺失，但是进程不会卡死」。Turn 未核实；原意保存于本会话 visualization 目录的 `profile-all-rank-review-20261103/user-request.txt`。

固定 base `2e9126f0a5915e1a7041689e8bb40694409eff58` + 未提交补丁 SHA256 `8726faf7cfbebed5fb3a4cda0a152c41c31298a8d89dc2e71b98f970280278a9`：RPC 分别设置本地 flag，每个 engine 在自己的 startStep 处睡 2 秒。MTP 的 startStep 位于本轮通信之前，通知到达时一个 rank 已过钩子、另一个未过，便会分别从 N+1 和 N 开始采样；2 秒足以排空各自已有工作也不会消除该差异。这是源码时序反例，未冒充 GPU 复现。原有 fanout UT 只检查通知参数，单 rank sleep UT 只检查暂停与取消，都不能证明跨 rank 的起始 step 相同。另有 first-come-first-served 忽略新会话但 RPC 仍回 OK 的既有行为，需在严格全 rank 成功语义下说明或反馈为失败。

本轮实际读了 R-REV-02/04/05/08/14、R-STA-01/07/08/09/12、R-TST-01/02/03 和所有权/配置相关正文；前三路 prompt 也列出这些绝对路径与 ID。规则已有跨 rank 通信顺序、并发活性与验证边界要求，属于此前验收范围漏检：实现了局部排空等待，却没有证明共同 step，不能因单 rank UT 通过推成分布式对齐。更新本复盘，不新增重复规则。后续必须分别说明本地排空、共同逻辑 step、RPC 部分失败后的活性；不能用固定 sleep 代替 step 协议，也不能只给收到 RPC 的 rank 加无超时 collective 来修复对齐。本轮是固定源码审查，未修改生产实现；已确认问题保持未修状态。

同版本多模型首轮进一步暴露了“读过规则后误判”：GLM 把各自排空推成共同 step；Kimi 已描述 N/N+1 反例，却以未经测量的“概率低”宣布严格要求满足。三个模型还都按类名和方法签名猜测 EmbeddingEngine 继承 EngineBase；实际声明没有基类，该 finding 被主 agent 回读源码驳回。不能把模型一致意见当作独立证据，也不能把源码推导写成实测。原始回答、纠正与裁决保留在上述 review 目录的 round-1 和 report.json；下轮必须从真实继承声明与钩子前后时序核实，不能只读方法声明或函数局部。

同一会话随后用户补充「我们假设所有 rank 都已经退出之前的 profile 流程」，并质疑 N/N+1 反例是否只在 A 已经 profiling 时成立。该前提排除了旧会话 busy/静默忽略这一项，不再将它作为当前场景的问题。回读 TorchProfiler.cc:363 与 NormalEngine.cc:929：MTP 每轮都会调用 startStep，未启用时立即返回；A 可在 RPC 前以关闭状态经过 N 轮调用，B 在 RPC 后才调用 N 轮，两者此前都完全退出 profiler，仍分别在 N+1/N 启动。此前“经过采样钩子”容易让用户理解成“已开始采样”，属于解释时没有交代初始状态；补充 enabled=false、has_profiler=false 的初态和先后顺序即可，不新增规则、不扩展修改。R-REV-02/05 与 R-STA-07/09 已覆盖前提及通信顺序；源码反例仍未作 GPU 运行复现。

同一会话用户再次明确：「我说的 step，是采集出来的 timeline 中，不同 dp 的 forward 是对齐的，和外面的计时器没关系」。这澄清了上述判断的验收口径：检查跨 DP 的实际 GPU forward/MoE 采样窗口能否对应，不要求外层 hook 或本地计数一致。此前主 agent 持续用 TP 内 CPU 钩子 N/N+1 解释并宣布需求不满足，没有完成它到用户所指跨 DP GPU capture 的证据链，属于读取规则后对需求对象的误判。撤回仅凭该论证给出的“不满足”结论；不因此反向声称已实测证明所有 DP 的首个 forward 对齐，也不因外层计数不同要求引入全局 step 协议。当前前提为旧 profile 全部退出、2 秒足以排空 worker；后续以实际 GPU forward/通信事件的对应关系验证。R-REV-02/04、R-STA-11 已覆盖对象与证据口径，无需新增规则。此澄清覆盖前两段将外层起始轮次直接作为本用户验收条件的表述，历史源码推导仍保留。


2026-11-03，同一 session 后续提交与本地 UT：按用户澄清的“实际 GPU forward 对应”口径，新增真实 StepWindowProfiler + 双进程 CUDA/NCCL 组件测试，区分旧尾部 sin、本轮 cos、下一轮 tanh；无 pause 负对照会捕获旧尾部，缺少一个 rank 通知仍能继续。进一步固定 df00dd8894 回查 MTP：启采钩子在 CPU TP 输入同步前。可达反例应选 TP 非 root 在未启用时经过 hook 后等待 UDS read；root 在 hook 前收到 RPC 并睡两秒，另一 DP 从本轮启采。不能默认 UDS root 的 write 会等待 peer。四 GPU 时序实验使用实际 profiler/CUDA/NCCL、两个 CPU Gloo 组模拟 UDS 等待：旧顺序下非 root rank1 捕获 tanh（N+1），rank0/2/3 捕获 cos（N）；移至输入同步后的顺序下四 rank 均捕获 cos。实验不是直接运行 MtpExecutor，结论边界必须保留。

该证据补齐了此前缺失的 CPU 钩子时序到实际 GPU capture 的链路，不撤销用户不要求外层编号相同的口径，也不据此增加全局 step 协议。修复 b4f3bef2db 将 MTP 首次实际采样移到 tpSync/skip 判断后、forward 前；同 process 的 prefill/decode 只启停一次、空闲轮不计数，回调保持 engine 线程。真实 gRPC 超时 UT 同时补上客户端 deadline 的覆盖，避免只返回一个假 DEADLINE_EXCEEDED 状态就声称无挂死风险。R-REV-08/14、R-TST-01/03、R-STA-11 已充分覆盖，前轮是证据链未闭合及 UDS 阻塞方向未核实；本次只记录真实案例，不新增重复规则。固定源码、首次失败、后续实测、原始模型问答位于本会话 visualization 的 profile-all-rank-submit-20261103；最终提交和最终 UT 结果以该目录 final-ut-command.json、验证汇总和 review 报告为准，未完成测试不提前计入通过。

最终干净提交 b4f3bef2db 在本机 11.163.39.112 实际运行 8 个 UT 目标、224 个用例，全部通过、无跳过；日志散列和 XML 已复核。CUDA runtime 实测能力 10.3。新增回调顺序断言直接覆盖 prefill、alignment-only 和 PDFUSION，一般 DSpark/普通 decode 的既有 UT 通过不等于新增回调顺序也被直接断言。固定 2 秒暂停不是跨 rank barrier；这批组件测试和四卡相位实验不能外推为任意通知延迟下的保证，也不能称完整模型 MoE smoke。源码修复收窄了可达窗口，未增加全局 step 协议。

2026-11-04，同一用户批评 MtpExecutor 内 profiler 钩子散落，随后明确要求「你先理清楚原来 async decode step，profiler 是怎么生效的，然后在考虑方案咋改啊」。Turn 未核实；raw: `/home/baowending.bwd/.codex/sessions/2026/11/03/rollout-2026-11-03T15-32-22-01a1a052-cad4-7752-8248-211e25971f3b.jsonl`。本轮按要求只读生产代码，固定原版 cd618a310b5e375c5a19872a83958f4cbda596f4，对照当前本地合并提交 309677804844220cefaaf3488658cf27767fb48e。新增代码确实将原先 NormalEngine 的一对启停调用扩成 MtpExecutor 的两个构造回调、一个每轮 guard 和四处分支入口；不能以测试通过替代对职责与改动必要性的解释。

回查原版得到的事实：MTP 的 startStep/finishStep 在 engine loop 线程包住 process；target/draft forward 或 graph replay 由该线程提交，AsyncRunner 主要承接准备与结果回写。AsyncRunner::sync 等待 CPU closure 结束，再向主 CUDA stream 插入 event wait，并不是 CPU 等整张 GPU 完成。原 TorchProfile::start 没有设备排空；窗口最后的 stopAndCollect 先 synchronizeDevice 再 disableProfiler，足以等待已提交 forward，但没有 join 尚可能继续提交工作的 CPU worker。后台 worker 禁用 RecordFunction 回调；AsyncProfileSession 只收集/截断额外事件，也不 join worker。NormalExecutor 原本在 TP 输入同步后启采，在异步 dispatch launch 后仍由 engine 线程结束采样。故“async 本身要求在每个 MTP 分支增加 profiler 生命周期”没有依据；跨 rank RPC 到达相位与原有异步收尾应分别论证。

本轮实际重读 R-MIN-07、R-STA-01、R-OWN-14、R-WRK-05，并核对原始调用链。现有规则足够；此前实现没有先完整说明旧生命周期与新增分支状态各自解决的问题，属于最小改动及所有权判断执行不足。不能仅凭本轮材料断言此前每路 reviewer 是否读过这些正文。本次补充复盘，不新增重复卡，不提前定重构位置，不把组件测试提升为真实 MTP forward 对齐证明。原版源码快照保存在本会话 `profile-all-rank-submit-20261103/async-profiler-baseline-20261104`；本轮未改生产源码、未提交、未执行 GPU 测试。

同日用户随后授权「好，你先修改一个版本，然后我再 review」。本地版本保留在 3096778048 上的未提交 diff：MTP 所有实际 model forward 统一经过 runModelForward，原有日志及输入变换不变；删除四处分支启采、MTP 自有去重标记与 finish 回调，由 StepWindowProfiler 对同一 process 的多次 start 去重，NormalEngine 负责 finish。去重必须在 disabled 快路之前记住首个 forward，否则中途 RPC 会从 target/commit 截取半轮。回查调用方发现 preRun 也直接执行 process，补齐该入口的 finish，并用真实 preRun + profiler 的测试验证下一轮能够推进窗口；不能只改主循环收尾。

最终补丁 SHA256 为 `8bcd6a56a854e4f8150a4e2cd03707c77aa0fcb2c269a485bcea315c92ad2c5d`。本机实跑四组 141 用例，以及单独筛选的 `NormalEngineTest.testMtpPreRunFinishesProfilerStep`，合计 142 个通过、无跳过。双卡组件测试中，两 rank 的单窗口均捕获三次 cos forward/NCCL，不含前后轮 sin/tanh；仍不是完整模型 MoE smoke。扩展 engine_test 全量在初版重构中崩溃；隔离原 HEAD 3096778048，同环境全量测试也在未修改的 `NormalEngineCustomOutputTest.testCustomOutputSelectedOnceBeforeSystemPrefix` 以相同退出码 245 失败。该全量失败不计入通过数，最终 engine 验证明确仅筛选新增 preRun 用例。源码补丁、两轮测试、基线对照及 final-verification.json 保存在本会话 `profile-all-rank-refactor-20261104`；临时基线工作区和分支已清理。此案例补齐 R-OWN-13 的全部调用方及 R-TST-01/03 的证据要求，不新增重复规则。

2026-11-04，同一 session 用户接受「默认关闭，开启后每 step 协调」，并补充「但是要保证这样 + rpc 通信，能够保证在同一个 step 采集」「可以把采样信息也放在 broadcaster 里，搞一个结构体」。这是对调试开销的明确新授权，覆盖此前不引入逐 step 协调的限制；验收对象仍是各 rank 的实际 forward 窗口。新版本恢复 MtpExecutor.cc/.h 及其测试到 cd618a310b 原版，由 NormalEngine 在调度等待前进入独立 Gloo CPU 通道。rank 0 在锁内冻结采样结构体，RPC 赶不上当前快照就选择下一轮；各 rank 启动 profiler 后再次确认，才放行对应 process。只有 all-rank RPC 指令携带两秒暂停，自动配置采样不携带；通道异常后停止复用，推理通信保持独立。

本机最终验证共 10 个目标、233 个用例通过，engine_test 只筛选 testMtpProfilerOwnedByEngine；此前已确认的全量 engine_test 基线崩溃不计入通过。四 GPU 组件测试运行生产 StepWindowProfiler、生产 CPU broadcaster 与 CUDA/NCCL，覆盖 follower 未收 RPC、root 快照后到达 RPC、本地采样冲突、连续两次采样，以及控制交换与启动确认失败。四个对齐场景各 rank 的目标 trace 均含三次 cos forward 和三次 NCCL，不含旧 sin 或后续 neg/tanh；紧接的第二窗口各 rank 均含三次 neg。失败注入后 NCCL forward 仍完成。组件测试没有运行完整 MtpExecutor 或 MoE 模型，不能把它称作整模型验证。首次绑定路径、共享库链接失败及设备锁冲突均保留；最终工作区源码散列、测试命令和日志存于 `/home/baowending.bwd/.codex/visualizations/2026/11/03/01a1a052-cad4-7752-8248-211e25971f3b/profile-cpu-sync-20261104`。该轮变更未提交，旧版模型审查和 CI 结果不适用于这份新补丁。现有 R-STA-07/09、R-OWN-14、R-TST-01/03 已覆盖协议、生命周期与验证边界，无需新增重复规则。

同日用户继续指出「我们都加了 dispatch 前同步了，为啥还需要 2s 的排空请求」，随后要求理清时序并设计完整方案。回读当前 HEAD a3815e61e1464f65c405fdfba2900da029800c5c 上的未提交实现、MtpExecutor、PyWrappedModel eager/graph 调用及 AsyncRunner：CPU 每轮协调证明各 rank 已走到相同提交边界；它不证明 GPU 已执行完毕。现有 MTP 的实际 model forward / graph replay 由 engine 线程提交，异步 prepare 在对应 forward 前 sync；process 返回后仍可继续的是结果回写等后台工作。因此按已约定的“forward 窗口”口径，固定 sleep 不应继续保留；方案应在共同采样轮启采前显式等待已提交 GPU 工作完成，再以 CPU READY 确认全部 profiler 启动。窗口末尾保留 GPU 完成等待与 profiler 停止，下一轮正常 CPU 交换阻止快 rank 在慢 rank 停采前提交下一轮 forward。

此前四卡 UT 把旧 forward 放在延迟启动的后台 CPU 线程中，能验证“两秒足以排空”假设下的旧方案，却不能据此证明真实 MTP 必须等待两秒或证明删除 sleep 后仍正确。这次是实现模型变化后未重新核实旧机制必要性，以及测试任务归属与生产路径不一致；已读取 R-MIN、R-OWN-14、R-STA-07/09、R-TST-01/03，规则并不缺失。本轮只形成方案，不改生产源码，不执行 GPU 测试。后续必须改为“旧 forward 已提交但 GPU 未完成”的测试夹具，并分别验证起止边界、真实 RPC 路由、超时后推理活性；旧 233 项通过不追认为新方案验证。GPU/NCCL 自身故障不属于仅靠 profiler 控制通道可恢复的 RPC 失败保证。


2026-11-04，同一 session `01a1a052-cad4-7752-8248-211e25971f3b`，用户进一步收窄需求：「我们其实不需要为这个东西设计这么复杂的功能……只需要把 enable_all_rank 时候，所有 rank 都采集 timeline 做了就行了，对齐可以靠 timeline 里的时间来对齐」，并要求在 engine.normal.execute scope 中加入 int64 累计 step。Turn 未核实；raw: `/home/baowending.bwd/.codex/sessions/2026/11/03/rollout-2026-11-03T15-32-22-01a1a052-cad4-7752-8248-211e25971f3b.jsonl`。这是新的验收口径，覆盖前面的跨 rank 同一 forward 窗口保证；不能继续据旧契约保留逐 step Gloo 协调、READY、固定两秒暂停或 MTP 生命周期钩子。

本轮读取 R-MIN-03、R-OWN-14、R-STA-01、R-TST-01/02/03，并回查 scope 宏：无 profiler callback 时不计算格式参数，计数自增必须放在宏外。计数由每个 NormalEngine 的 engine loop 单独持有，跨采样窗口持续递增；它是各 rank 自身的执行序号，不声明为分布式统一编号。已有规则覆盖职责和删除旧机制，不新增重复规则。旧协调实现已快照后移除，MtpExecutor、TorchProfiler、EngineBase 接口恢复到 cd618a310b；保留 world 地址命名、全 rank RPC 路由和非致命 deadline。后续验证记录见本会话 `profile-simple-all-rank-20261104`，旧版 233 项通过不追认为当前实现已验证。

该简化版本本机实跑 6 个 UT 目标、81 个用例全部通过，无跳过；engine_test 仅筛选新增 testExecuteStepPersistsAcrossProfilerWindows。该用例执行真实 NormalEngine::step 和 CPU Kineto 采样，executor 替换为无操作实现，验证未采样时仍递增、跨两个采样窗口不重置，以及 631152000000 以上的 64 位 scope 名称；不宣称运行了完整模型 forward。RPC 测试保留四服务 TP/DP 路由、错误返回和真实三秒 deadline。最终补丁 SHA256 为 390b69632dd37e7d3371a856ea0e5fb4a21650204ddfb6a0dac10f7a985186aa，源码、实际命令、XML 和日志已存于 profile-simple-all-rank-20261104；未提交、未启动新 CI，也未引用旧版多模型 review 作为当前结果。

同日用户追问 world-size BroadcastManager 是否只在发起 rank 创建，以及每次请求创建后销毁是否浪费。回查 BroadcastManager 和 LocalRpcServiceImpl：它是 gRPC fanout 客户端，接收 rank 已有 StartProfileInternal 服务，因此各 rank 对称创建客户端不是必要条件；请求局部对象却会重复创建 RPC pool 和 completion thread，生命周期应随 LocalRpcServer。按 R-OWN-01/02 和 R-MIN-03 改为 unique_ptr 成员，在首次 all-rank RPC 时通过 std::call_once 创建；普通 step 与未启用 all-rank 的 RPC 不创建它。旧规则足够，此前对请求局部资源成本判断不足，不新增重复规则。新增重复请求复用、并发首次创建以及失败后成功重试用例；最新 local_rpc_server_test 实跑 41 项通过。开源提交 8d18196ebf7070d27fd1156abd82943543f7c548，证据存于本会话 profile-reuse-smoke-20261104。真实模型 smoke 尚未完成，不能把 RPC UT 或旧实现 review 当作整模型验证。

上述 8d18196ebf 版本随后在 BBDetector 11.163.39.114 的 bbdev_baowending_bwd 容器真实运行四 GPU CP2 prefill + TP1/DP2 async decode，使用经索引、分片大小和 tokenizer 验证的 3FS DeepSeek-V4.1-Flash。一次 enable_all_rank RPC 配置 10 step，两个 decode rank 均输出 10 个连续 engine.normal.execute(step=...) 与 10 个 executor.mtp.process(stream_size=...)，GPU kernel 分别 9151 / 9076；两条请求均完成 512 token。两 rank 的本地 step 范围不同，这是已收窄契约允许的结果；trace 共享时间基准。初版测试驱动错误地用 is_streaming 参数及过宽的 process( 事件前缀，分别导致未接收 SSE 和把 report_metrics scope 重复计数；根据生产 RequestExtractor 的 yield_generator 契约和精确 scope 名称核实修正。复用存活服务的独立客户端完成这一轮采集；没有把未执行的第二窗口计为通过，重复复用仍由 41 项 RPC UT 验证。初次 stop 后的退出仍有延迟，最终按 PID/create_time 复查所有本任务进程均退出，GPU 4–7 无进程。证据、原始失败、两份 trace 与 final-verification.json 均存于 profile-reuse-smoke-20261104。此为测试断言与实际执行单位不一致的 R-TST-01/02 案例，不更改生产代码来迎合错误断言。


## 已核对案例：采样宽度契约与 temperature gate 的实际命中

来源：session `01a1b02a-df10-7022-b24a-761ab088d0dd`，2026-11-06，Turn 未核实。用户要求「force topk这个直接改默认值1024就行了，mtpexecutor不要额外加判断」，支持 512/1024/4096、环境变量只接受关闭或这些值，并要求 temperature 折叠覆盖 0/1。raw: `/home/baowending.bwd/.codex/sessions/2026/11/06/rollout-2026-11-06T17-22-42-01a1b02a-df10-7022-b24a-761ab088d0dd.jsonl`，第 11 行。

基线 `40fd345324` 的环境解析默认已经是 1024，但 draft 调用方用 `min(1024, configured_k)` 再次截断；fused sampling gate 与内部断言又单独写死 1024。用户指定的支持集合应由配置边界校验，native wrapper 按对应模板 dispatch，调用方不再改写显式值。temperature gate 拒绝整个含零温度的 batch，使 rank21 的九个稳态 step 都保留全词表温度 kernel。这个结论由融合 target 分支、无 penalty kernel、无 masked_select/masked_scatter 联合推导，不能声称 trace 直接记录了请求温度。

已读 R-MIN-01/02、R-CFG-01/02/03/04、R-TST-01/03/05。现有规则覆盖配置单一来源、边界契约与验证范围，无须新增规则。此前没有完整读取证据，无法区分未读与误判；这次扩大支持宽度后的首轮 UT 还抓到了漏改的 target 内部 `size(1)==1024` 重复校验，说明只改 dispatch 并不足够。已去掉重复校验，CUDA wrapper 保留输入契约；新增真实三档 GPU 路径和混合 0/1 温度分布测试。首轮失败记录必须保留，修改后通过情况以测试日志为准。

证据：`/home/baowending.bwd/.codex/artifacts/sampling-review-20261106/` 中的 `rank21-audit.json`、`rank21-correlated.json`、`tested.patch` 与 `ut.log`。相关时间是 profiler 中的 kernel 耗时，不是无 profiler 的端到端收益。

## 已核对案例：删除指定条件时误删相邻 guard

来源：session `01a1c468-fb51-7590-bfc0-88d817cc135b`，2026-11-10，本会话用户消息，Turn 未核实。用户先要求 compact_target「不需要 mixed_sampling / any_top_p」，随后指出「no_explicit_top_k 还是要加上的吧？」。

主 agent 把整个内部判断替换为 true，误删了用户未要求删除的 no_explicit_top_k，并同步改错测试预期，提交为 67bbc4641e。修正提交 3a1475db05 恢复 compact_target = no_explicit_top_k：显式 top-k 保持 full-width，无显式 top-k 时不再要求 any_top_p。映射限制的测试改用无显式 top-k 输入，避免被另一个条件遮蔽。

本轮修改前已读取 R-MIN-01、R-MIN-03、R-WRK-03 和 R-TST-01/02。现有规则足够，归因为读后误判和扩大修改范围；编译通过只证明可编译，不能发现把需求与测试一起理解错的问题。不新增重复规则。以后删除复合表达式中的指定条件，先写出修改后的表达式，逐项核对保留条件，再调整测试预期。

修正后的 CUDA13 normal_engine compilation_outputs 构建通过；完整库构建受 KVCM 依赖接口不匹配阻塞，未运行 GPU 测试。日志：/home/baowending.bwd/RTP-LLM/build_logs/compact-target-no-topk-objects-20261110.log。


## 已核对案例：采样后端宏散落在业务编排中

来源：本会话用户可见消息，2026-11-10（Asia/Shanghai），Turn 未核实：「另外为啥代码里有这么多using cuda?这个不合理吧」。工作区 `/home/baowending.bwd/new/RTP-LLM/github-opensource`，基线 `448a7e4de9ef0fbd99b460b9c9a09ff2ff516889`。

核对发现 Sampler.cc 本轮新增一处 USING_CUDA，把 compact 布局选择与编译后端绑在一起；SpeculativeSampler.cc 原有 18 处相关条件编译，本轮剩 15 处，draft eager 内仍直接调用 cuBLAS、DeepSelect、FlashInfer 和 CUDA stream。已有 ExecOps 采样入口可作为集中后端实现的边界。ROCm/generic sampleGreedy 当前没有 compact 实现，故不能直接删除宏，否则上层分配的候选 indices 没有对应写入方。应收拢完整后端实现与布局分配责任，避免逐个 kernel 增加空转 wrapper 或能力注册表。

本轮实际重读 R-MIN-06、R-OWN-13/14 及反馈路由。此前侧重消除重复采样条件，却沿用上层穿插后端实现的结构，属于职责边界复核不足。现有分层原则足够，不新增“所有 CUDA 宏都不合理”的规则；真实 CUDA 类型、头文件和后端编译单元仍需构建隔离。本轮仅核对和解释，尚未实施后端抽离。

后续同一会话用户要求先把 compact 相关宏统一为 `ENABLE_COMPACT`，并明确选择「按构建后端：CUDA 开，ROCm/CPU 关」，再次确认与 SM 无关。本轮按该明确范围实现：SamplingConfig.h 集中定义，Sampler 的布局选择及 draft eager 的配套分支使用该 flag，graph/confidence 的后端宏保留；没有扩成后端抽离，也没有把开关绑定 SM100/SM103。两份 sampler 源码去除 include 后的预处理正文在 CUDA/ROCm/CPU 三种定义下均与替换前一致；CUDA 完整构建通过，其他后端仅验证宏和正文选择，不能称为其他后端完整编译通过。

同一会话随后明确纠正：「我的意思是做成一个flag，不要用宏判断了，就是enable_compact() && xxx 这样」，并要求「最终只有一处判断，prefill/decode可以共用函数 or 共享一个flag」。此前只把 USING_CUDA 改名为 ENABLE_COMPACT，没有解决业务层条件编译与重复策略，是对用户目标的理解偏差，不能把宏别名当作普通布尔接口。本轮重读 R-MIN、R-OWN、R-CFG-04、R-REV-10 及本反馈路由；规则足够，不新增重复规则。改为 SamplingBackend 后端函数隔离 CUDA 符号，compactSamplingWidth 集中布局策略，draft/target 共用；target prefill/decode 同走 Sampler::forward。canFuseCompactSampling 只判断融合 kernel 能力，不能混同布局启用策略。原始全词表概率与累计 logprob 等真实输出契约仍保留。两路只读 review 发现抽离时将可变 fallback 标志误改为 const，已修复；首轮实际编译还发现 cuda_impl 的 filegroup 引用缺少新库依赖，已补齐。静态 review 不等于构建或测试通过，验证以本轮 sampling_compact_function_20261110 日志为准。

该修正版最终 CUDA 构建通过，GPU 三组去重 103 项通过、1 项多 GPU 用例因单卡跳过；新增 draft/target、step=0/2、K=0/512/1024、p=1/0.9 对照通过。首版新增 UT 使用 arange/1000，以严格容差比较 draft 的既有 FP16 selector 与 target FP32 selector，失败由代码确认的量化差异解释；改用 FP16 精确可表示的 arange/1024 隔离本次策略收敛，保留原严格容差及生产算法。首轮失败与最终结果均保存，不抹除失败记录。通用后端使用 USING_CUDA=0/USING_ROCM=0 独立编译并实跑布局关闭、过滤、GEMM、commit fallback；未做完整 CPU/ROCm 工程构建。证据目录 `/home/baowending.bwd/new/RTP-LLM/build_logs/sampling_compact_function_20261110_results/`，包括源码补丁、binary/source SHA256、两轮 XML 与 verification.json。

## 已核对案例：MTP packed sampling 的布局边界

来源：session `01a1c90c-cc18-7063-8df2-30bdbddc6977`，2026-11-11。用户指出「你改的范围过宽了」，要求在 `sampler_->forward` 前后分别 gather 参数、scatter 输出，只有边界和 `applyMaskToLogits` 感知 packed 映射。raw: `/home/baowending.bwd/.codex/sessions/2026/11/11/rollout-2026-11-11T13-20-21-01a1c90c-cc18-7063-8df2-30bdbddc6977.jsonl` 第 1132 行；第 1283 行授权实现、UT 和 BS64/128 性能对比。

上一版把行映射传播到 sampler、拒绝采样和图缓存，以省掉输出还原。这扩大了接口契约；用户选择保留 dense 下游后，应撤掉这些传播，不能同时留下两套坐标。R-MIN-07、R-OWN-05/15 已覆盖边界和单一数据来源，本次属于实现边界选择失误，不新增通用规则。新边界仍须处理 CPU dispatch 摘要、按原 dense 行数预留 RNG、历史 token 和无效行初始化，不能把它简化为只 gather 三个标量。ThinkState 是任务开始前的未跟踪文件，不能归因于该实现；已依据原始状态备份隔离。性能结论以本轮实际 kernel 测量为准，不凭全词表输出大小推断必然退化。

## 已核对案例：MTP 反向映射的必传出参

来源：同一 session 第 1960 行，2026-11-11 11:07:23 UTC，用户指出「一个&一个*你这个代码质量有点离谱吧」，截图为 `gatherSpecSamplerInput` 的 `const torch::Tensor& packed_to_dense` 与 `torch::Tensor* dense_to_packed`。raw 路径同上，Turn 未核实。

这里的具体问题不是引用和指针不能出现在同一签名，而是输出并没有独立的“不收集”语义：packed 分支必需生成映射供 mask/scatter 使用，原接口却给出 `nullptr` 默认值，再在分支内断言非空。dense 分支不生成映射，也没有清除调用方复用张量中的旧值。改为必传引用，入口置为 undefined，删除判空和解引用；同步生产调用及 35 处测试调用，并在原有 dense 历史用例中检查复用输出被清空。

本轮读取 R-MIN-01/07、R-OWN-03/13、R-TST-01/02/03 和反馈路由。原 session 第 68 行有完整读取 30-ownership.md 的记录，因此属于已读后未落实，不是规则缺失。给 R-OWN-03 的例外补充分支不产出与可选收集的区别及本次来源，不新增规则。此次修改不改变 CUDA kernel；验证证据位于 `/home/baowending.bwd/packed-sampling-work/reference-output-fix/`，测试结果以该目录记录为准。

## 已核对案例：packed mask 的重复类型调用

来源：session `01a1c90c-cc18-7063-8df2-30bdbddc6977` 第 2219 行，2026-11-12 10:26:24 Asia/Shanghai，Turn 未核实。用户要求 `CudaOps.cc` 的「invokePackedMaskLogits改成用宏写吧？现在这段代码都是重复」。raw: `/home/baowending.bwd/.codex/sessions/2026/11/11/rollout-2026-11-11T13-20-21-01a1c90c-cc18-7063-8df2-30bdbddc6977.jsonl`。

三个 dtype 分支只有 kernel 类型和 Torch 指针类型不同，添加映射参数却需要重复修改三份参数列表。本轮按用户要求用局部宏保留一份调用，使用后立即 undef；保持 FP32/FP16/BF16 支持范围及原异常行为。读取 R-MIN-07、R-OWN-13/14 和反馈路由后，归因为沿用既有重复实现时未收敛参数列表；这是可维护性和项目实现偏好，不能声称旧代码已有采样错误，也不新增“所有类型分派必须用宏”的通用规则。仅改该处代码，复用现有三 dtype mask UT 和 MTP packed UT 验证。增量补丁和验证证据目录：`/home/baowending.bwd/packed-sampling-work/packed-mask-macro-20261112/`。

## 已核对案例：packed mask 内部入口的重复校验

来源：同一 session 第 2451 行，2026-11-12 11:27:30 Asia/Shanghai，Turn 未核实。用户指出「launchPackedMaskLogits和validatePackedMaskLogitsInputs这个里面，有些没用的校验全部删了吧」，要求核查可达路径。raw: `/home/baowending.bwd/.codex/sessions/2026/11/11/rollout-2026-11-11T13-20-21-01a1c90c-cc18-7063-8df2-30bdbddc6977.jsonl`。

此前只修正 identity 映射的断言文案，没有重新判断该层校验是否必要。全仓调用搜索确认只有 GrammarLogitsProcessor 与 SpecLogitsVerifyRunner 两个生产入口：前者检查 logits 布局和词表范围，后者检查任务尺寸；mask、索引和设备位置均由内部构造保证，无 active 的路径提前返回。删除整个 validator、launcher 中重复的设备/映射检查及空 mask 分支，在头文件说明输入约定。kernel 对负数行号和 `dense_to_packed == -1` 的跳过属于正常映射语义，保留；上游真实词表错误也保留。

本轮已读 R-MIN-01/03、所有权与契约规则及反馈路由；现有规则充分，归因为沿用旧校验并只修文案，未按调用链落实边界只检查一次，不新增规则。五组既有 UT 覆盖 CPU/CUDA mask、MTP packed sampling 和两个生产调用方；最终结果以 `/home/baowending.bwd/packed-sampling-work/packed-mask-check-cleanup-20261112/verification.json` 为准，不沿用删除前的通过记录。


## 已核对案例：MTP packed sampling 的后端宏与 kernel 计数

来源：session `01a1c90c-cc18-7063-8df2-30bdbddc6977` 第 2625 行，2026-11-12 14:28:10 Asia/Shanghai，Turn 未核实。用户问「preparePackedMtpSampling为啥套了USING_CUDA宏 没用吧」和「他到底引入了多少个kernel」。raw: `/home/baowending.bwd/.codex/sessions/2026/11/11/rollout-2026-11-11T13-20-21-01a1c90c-cc18-7063-8df2-30bdbddc6977.jsonl`。

normal_engine 的 BUILD 在各后端 glob speculative/*.cc，CUDA kernel 依赖却仅由 using_cuda 选择；该函数直接使用 CUDA stream 和 CUDAGenerator，因此不能把实现及调用宏直接全部删除。头文件声明只含通用 Tensor 类型，其宏没有独立的类型隔离作用。业务调用点的宏来自实现只在 CUDA 下提供，若收敛应在后端实现和构建边界处理，不能把空实现当作非 CUDA 支持。

按当前融合生产路径源码计数，prepare 每次只 launch 一个 gather 模板实例，逆映射和可选历史展开在同一 launch 内；CPU 参数整理及 RNG 预留不 launch，浮点/整数/RNG staging 是 2 或 3 次 H2D，有历史再加一次 H2D。生产 fused prepare 提供连续 CUDA proposals，draft.to(...).contiguous() 不拷贝；非连续 CUDA draft 则可能多一个 copy kernel。采样后的 scatter 单独再 launch 一次，不能计入 prepare，也不能把两种模板实例说成每次两个 kernel。读取 R-MIN-06/07、R-OWN-14/15 和 R-TST-03 后，现有规则足够，记录构建隔离与运行时能力的区别；本次只解释源码，没有修改生产代码或新增实测。


后续用户指出「为啥采样模式汇总，上传temperature等要放在sampler里面做，看上去很割裂啊」（同一 session 第 2725 行，2026-11-12T06:42:20.169Z（UTC），Turn 未核实，raw 路径同上）。核对发现旧入口接收 CPU 参数，在具体采样分支中汇总模式并按需上传，能避免上传未使用的 temperature/penalty；这不代表准备必须散落在执行阶段。当前 packed 版只将一部分准备前移，用 optional prepared 同时承载 CPU 原始输入与 GPU 已准备输入，增加重复归一化逻辑和分支。R-OWN-14/15 已覆盖职责与同类路径一致性，此前为缩小改动保留双重契约，属于设计取舍未收敛，不新增规则。本次建议让采样模块提供所有路径共用的显式准备阶段，按实际采样子 batch 汇总并按需上传；packed 在该阶段后 gather，forward 消费统一输入。RNG 仍须在压缩前按 dense 行数预留。这里只分析职责，未实施重构，也未把源码分析当作测试通过。


同一会话第 2801 行（2026-11-12T06:53:24.513Z，UTC，Turn 未核实）用户进一步要求「dense_to_packed和packed_to_dense生成要在同一个地方，不应该一个在外面一个在gatherSpecSamplerInput里」。此前为减少 launch，把逆映射写入 sampling gather，导致正反两张布局表由不同阶段构造，gather 的输出参数还承担布局所有权。重读 R-OWN-14/15、R-MIN-01、R-STA-08、R-TST-03 后，归因为只优化 launch 数而未统一数据所有权；已有规则足够，不新增规则。本轮将两表统一交给 DSparkPackedTargetLayout：融合布局 kernel 同时写出正向、逆向映射和 -1 哨兵；Torch fallback 在同一布局函数构造两表；采样 gather 只消费映射。公共准备入口显式生成每个 single-beam 子 batch 的模式和设备参数，替换 optional prepared；最终测试与 kernel 计数以 `/home/baowending.bwd/packed-sampling-work/unified-preparation-20261112/` 的本轮证据为准。


同一会话第 3233 行（2026-11-12T07:23:08.355Z，UTC，Turn 未核实）用户要求「大部分地方其他arch也能够编译，真的涉及到kernel的地方再用ifdef cuda 拆分，上层的路径选择应该用enable() flag来选择」。此前虽识别整文件宏范围过大，实施公共准备时仍用宏隔离声明、参数分组和调用点，属于已知职责问题未落实。本轮读取 R-OWN-14/15、R-MIN-06、R-CFG-04 及本反馈路由；已有规则足够，不新增重复规则。改为单一后端能力函数 enableDeviceSampling()：普通采样准备、MTP 布局和采样输出路径使用普通布尔分支，不添加环境变量；公共参数整理与 Tensor 分配在各后端编译，宏只保留在 CUDA 专属 RNG、stream/kernel 和后端实现处。非 CUDA 收到 packed logits 时恢复原 dense logits 路径；未实现的 kernel 入口显式报错，不能留下空操作。独立非 CUDA 编译和本轮 UT 证据放在 `/home/baowending.bwd/packed-sampling-work/backend-flags-20261112/`；CUDA/CPU 用例结论以最终 verification.json 为准，不能等同于完整 ROCm 工程验证。raw 路径同上。

本次最终 CUDA 223 项与 CPU 9 项通过，单卡运行跳过 1 项多卡测试；packed 文件在不提供 CUDA 头文件、USING_CUDA=0/USING_ROCM=0 下独立编译通过。新增 CPU 用例首轮把温度倒数误写为 1/T，依据既有 SampleTemperature.h 与 kernel 的 epsilon 契约修正为 1/(T+1e-6)，未修改生产计算、未放宽比较，重跑 9 项通过；首轮日志与最终日志均保留。没有做完整 ROCm 构建或运行验证。

## 已核对案例：采样执行参数保留两个并行结构

来源：session `01a1c90c-cc18-7063-8df2-30bdbddc6977` 第 4200 行，2026-11-12T08:21:31.394Z（UTC），Turn 未核实。用户肯定判断和 device 转换已集中到 gather input，随后指出「引入了sampling这个莫名其妙的东西，里面还是一堆未切分的tensor，要靠sampling.ints.select(0, 0)去取；并且还是保留了GreedyParams；他们明明应该是同一个；这个设计是不合理的。应该只有一个GreddyParams」。最后一个类型名按原话保留，代码中的名称为 `GreedyParams`。raw: `/home/baowending.bwd/.codex/sessions/2026/11/11/rollout-2026-11-11T13-20-21-01a1c90c-cc18-7063-8df2-30bdbddc6977.jsonl`。

意见成立。固定旧快照的 `OpData.h:309–330` 同时定义 `SamplingDeviceParams` 和带 `top_k`、`top_p` 等具名字段的 `GreedyParams`；`CudaSampleOp.cc:790` 的执行入口同时接收两者，`:560–561` 再通过 `sampling.ints.select(0, 0)`、`sampling.floats.select(0, 0)` 取参数。准备阶段前移后，参数语义仍分散在两套结构和多处列号解释中。当前没有证据证明这种结构已造成采样错误；这是明确的接口收敛要求及维护成本问题。单个 staging 张量可以用于合并上传，关键是准备结束后暴露具名 device Tensor，执行消费者不再解释该内部布局。

本轮读取 R-OWN-05/11/14/15、R-MIN-01/03/04/06/07/08 及本反馈工作流。R-MIN-06 已直接要求复用已有输入结构；R-OWN-05、R-OWN-11 要求单一来源和职责收敛，R-OWN-14/15 要求分层及同类路径契约一致。规则与入口已经覆盖，无需增加“所有 host/device 数据都必须共用结构”或“禁止 SoA”的通用规则。准备与执行是两个真实阶段，也不应因 R-OWN-11 而重新合并成在采样中上传。

可回查的主会话第 68 行请求读取完整所有权规则，第 72 行输出可见 R-OWN-11/14/15 正文；第 2729/2733 行在讨论前置准备时再次读取 R-OWN-14/15。后续第 3599 行的定向读取选择了 R-OWN-03/13/14/15，未列 R-OWN-05/11。可确认的问题是已经读取职责规则后，设计检查停在阶段与映射边界，未收敛执行参数；不能仅凭早期整篇读取命令断言 R-OWN-05 的正文未被截断，也不据此评价各模型是否漏读。用户这次进一步明确“一个 `GreedyParams`、具名 device 字段”，应作为本项目当前约定，不追认为此前已承诺的逐字要求。

本轮只更新复盘，规则正文和入口不变。旧源码五个文件及 SHA256、用户完整原话、实际读取定位和裁决保存在 `/home/baowending.bwd/packed-sampling-work/review-20261112-154519/feedback-unified-greedy/`。下一轮对照新实现检查：CUDA 执行入口只接收 `GreedyParams`，普通与 packed 准备产出同一组具名 device 字段，转换与模式汇总仍在执行前，RNG 仍按压缩前 dense 请求次序预留，其他后端保留已支持的行为。此次维护不修改生产源码或测试，不提交；规则校验通过仅证明 skill 结构有效，新实现与验证结果由后续源码快照单独记录。


## 已核对案例：采样测试构建开关与 KV 源码改动的区别

来源：session `01a1c90c-cc18-7063-8df2-30bdbddc6977` 第 4566 行，2026-11-12T08:41:21.010Z（UTC），Turn 未核实。用户问「你咋能改到kv cache manager ?? 是不是有点牛逼了」。raw: `/home/baowending.bwd/.codex/sessions/2026/11/11/rollout-2026-11-11T13-20-21-01a1c90c-cc18-7063-8df2-30bdbddc6977.jsonl`。

用户要求守住采样优化范围成立；“已经修改 KV cache manager”这一前提经内外仓 git diff 核对不成立。KV 源码、.bazelrc、internal_source/.internal_bazelrc 与 internal_source/deps.bzl 均无本轮差异。首次构建遇到启用的 remote KV cache RPM 与源码接口不匹配，后续只在测试命令中显式传 `--define=use_remote_kv_cache=false`，未改依赖版本或持久配置。此测试结果不覆盖 remote KV cache 集成；不能把命令选项说成源码修复，也不能凭关闭开关后的通过宣布原依赖问题已修复。

本轮重读 R-WRK-03、R-DIF-01 和 R-REV-08，已有规则要求范围最小、回读证据及明确回答是否改动，无需增加重复规则。记录为范围核查与沟通澄清，不虚构无关代码已改或已回退。后续报告应分开写代码差异、测试命令与覆盖限制。用户原话及两仓文件清单保存在 `/home/baowending.bwd/packed-sampling-work/review-20261112-154519/feedback-kv-scope/`；未读出的历史意图不作归因。


上述单一 GreedyParams 整改的后续验证：最终补丁 `d9a27066610eae1b7b5e5dc49171ee9d5b20b5dff421ac2edc12bc62d39d5dcf` 已删除 SamplingDeviceParams 和双参数执行入口，普通与 packed 准备均填具名 device 字段；staging 的列号只留在准备阶段内部。CUDA 默认构造/forward 也撤出不再使用的 RNG 轮转 pool，非 CUDA 原消费路径保留。最终实跑 CUDA 421 项、CPU 9 项通过，1 项多设备用例跳过；24 组 kernel 对比完成，非 CUDA 单文件语法编译通过，未做完整 ROCm 验证。前三个旧 UT 读取上传前 CPU token 别名、一个普通 gather UT 要求 CPU/pinned，均按新契约同步；保留所有 token/probability/history/ngram 数值断言和首轮失败记录。证据为 `/home/baowending.bwd/packed-sampling-work/unified-greedy-20261112/verification.json`。该补记说明实现与测试已完成，不代替尚在进行的 GLM 第二轮模型结论；代码未提交。


## 已核对案例：enableDeviceSampling 混合后端契约与旧缓冲路径

来源：session `01a1cf0a-5a14-7642-9aa6-f22b2a7f316f`，2026-11-12，Turn 未核实，原始用户消息第 14 行。用户原话「看下现在代码diff区enableDeviceSampling管理的是什么，为什么需要他，我看他现在在遍地拉屎」。raw: `/home/baowending.bwd/.codex/sessions/2026/11/12/rollout-2026-11-12T17-15-24-01a1cf0a-5a14-7642-9aa6-f22b2a7f316f.jsonl`。源码快照、SHA256 和实际读取规则保存在 `/home/baowending.bwd/packed-sampling-work/device-sampling-review-20261112/review.json`。

`enableDeviceSampling()` 在 CUDA 构建恒真，其余后端恒假，没有运行期配置。当前未提交 diff 用它同时决定设备参数准备、旧 RNG buffer 生命周期、MTP packed 行处理、history 省略和概率输出格式；其中若干判断只是把原有 `#if USING_CUDA` 换成普通条件。不能因此说原来没有后端差异，也不能把 ROCm 误称 CPU 采样。ROCm 的 temperature/top-k 等仍有 CPU 读取，直接取消所有保护会破坏契约。`Sampler` 构造和 `forward` 都跳过 CUDA 旧 buffer pool，因此池内 CUDA 分配/轮转/pending 分支在生产调用链不可达；测试通过暴露私有方法直接覆盖它们，不等于生产仍需要。

本轮读取 R-REV-02/05/06、R-MIN-03/07/08、R-OWN-06/08/11/14/15、R-STA-08、R-CFG-04。现有规则足以支持职责收敛和死分支清理，不新增规则；R-CFG-04 的运行期配置禁令不能直接套在此编译能力查询上。建议让采样准备入口吸收后端差异，并让 packed 恢复依赖实际采用的采样布局，清理旧生产不可达分支及对应过期测试。旧实现的读取记录本轮未核对，无法区分未读与误判。此次只读审查生产代码，未修改生产实现或运行测试，结构观察不声称已复现数值错误。


## 后续核对：MTP 后端判断集中为一处 if/else

来源：主会话 `01a1c90c-cc18-7063-8df2-30bdbddc6977` 第 5306、5339 行，分别为 2026-11-12T09:20:23.589Z、09:22:51.818Z（UTC），Turn 未核实。用户先贴出上述 enableDeviceSampling 审查并要求“先看下这个问题”，随后明确“他应该是一个单一的if else，不该有这么多”。raw: `/home/baowending.bwd/.codex/sessions/2026/11/11/rollout-2026-11-11T13-20-21-01a1c90c-cc18-7063-8df2-30bdbddc6977.jsonl`。公开原话、源码与 hash 保存在 `/home/baowending.bwd/packed-sampling-work/review-20261112-154519/feedback-device-sampling/`。

意见成立。冻结补丁 `d9a27066610eae1b7b5e5dc49171ee9d5b20b5dff421ac2edc12bc62d39d5dcf` 中，同一个后端判断散落于 MTP 历史省略、采样布局、概率格式和参数上传；executor 又据后端和模型布局推断输出是否需要恢复。前次“撤出 CUDA pool”仅指构造/forward 不再使用，allocate/next 内的 CUDA 轮转与 pending 队列仍在，不能说冗余机制已经全部删净。直接调用私有 pool 方法的 UT 不能证明生产可达。

本轮读取 R-MIN-03、R-OWN-11/14/15 及反馈入口；前轮已有所有权规则读取记录，复盘判为职责规则读后落实不完整，规则与路由充分，不新增重复规则。“单一 if/else”作为本项目本轮约束记录，不推导为所有后端实现只能有一个条件。建议公共参数收集后集中分派完整准备路径，CUDA 内部保留 packed/penalty 等业务判断，另一分支维持既有非 CUDA 契约。mask 与 executor 使用 MTP 准备阶段实际选择的采样布局；非 CUDA 可能先将 packed 模型 logits 恢复 dense，不能直接拿模型 mapping 的 defined 状态替代实际采样布局。映射仍不进入通用 Sampler/GreedyParams，正反表仍由同一布局阶段生成。

按用户“先看”要求本次只核查并提出方案，未修改生产或测试。430 项 UT 的既有通过记录不能证明本项尚未实施的收敛已通过。下一轮实施需清理旧 CUDA pool 内部不可达分支及相应过期测试，同时保留非 CUDA 缓冲需求，并验证两条准备路径与实际布局恢复。


## 后续实现：MTP 单一后端分派与 sampler 输出所有权

来源：主会话 `01a1c90c-cc18-7063-8df2-30bdbddc6977` 第 5450 行（2026-11-12T09:40:55.025Z）明确“设计一个方案然后开始执行”；第 5780 行（09:59:00.433Z）指出 `all_probs`、`all_probs_point_mass`、`all_probs_indices` 是 sampler 内部输出，要求 gather 只构造通用输入。Turn 未核实。raw 与完整原话保存在 `/home/baowending.bwd/packed-sampling-work/review-20261112-154519/feedback-probability-ownership/user-feedback.json`。

意见成立。前一版虽将后端条件集中成一处 if/else，但仍在 gather 中推导 point-mass/compact 并分配输出。主 agent 已读 R-OWN-14/15，却只核对后端、映射和参数准备，输出所有权检查没有落实。现有原则足够，R-OWN-14 的判定只偏重上层概念下沉，本次补上反向泄漏的检查及人类证据，不增加新规则。显式 caller-owned output API 仍可由调用方提供缓冲；本例没有这项需求，不能借性能例外把内部工作空间塞进输入。

round8 补丁 `76326107070a4e39945b07ee2629487c33244abde21524c10fc200caf3add559` 删除三个 SamplerInputs 字段，输入只声明 NONE/DENSE/DISTRIBUTION 输出需求。普通返回概率要求 DENSE；MTP rejection 接受 DISTRIBUTION，d2t 要求 DENSE。forward 根据已准备的 mode 选择表示和局部分配；结果仍通过 SamplerOutput 返回。采样模式汇总、device 参数准备及 dense RNG 次序保留在 prepare。MTP 仅一处后端分派，实际布局随结果返回供 mask/restore 使用，旧 CUDA pool 内部分支和过期夹具已清理。DeepSeek 找到 benchmark 遗留旧字段导致编译失败，已同步删除并实际构建短运行；保留首次 const-list 编译失败及修复记录。

最终源码实际执行 430 项 UT 通过、1 项 benchmark 短运行通过、1 项多GPU用例跳过；2 项既有 disabled 未运行。测试断言从 gather 的内部缓冲移到真实 forward 输出，并新增全部概率模式、准备参数不被输出绑定污染的验证。完整 ROCm/模型 smoke 未执行；Sampler.cc 的 CPU-only 语法尝试被既有 CUDA graph shim 的 SDK 依赖阻塞，不能记为非CUDA编译通过。证据：`/home/baowending.bwd/packed-sampling-work/sampling-boundary-20261112/verification.json`。独立最终增量 review 此刻仍在运行，测试通过不替代模型结论；未提交代码。


后续验证（同一任务，round11）：上述430项UT结果属于round8，独立review建议给温度变体增加真实forward/token断言。新增后round10在B=8、V=4失败，暴露既有温度kernel按block线程数只加载前4行共享温度的缺陷；不能用准备输入字段正确推导数值执行正确。round11对scalar/half2两分支改为步进加载，补FP32/FP16直接数值回归；完整CUDA重新构建执行422项UT通过，CPU生产依赖未变，沿用round8的9项通过，另1项短benchmark通过。最终补丁 `405f051dab08571b8ad19807408aa530a6c6d9df333ed0b01256ee2f8d659216`，证据 `/home/baowending.bwd/packed-sampling-work/sampling-boundary-20261112/verification-round11.json`。旧失败日志保留，模型最终增量复核仍在进行。该补记是验证证据更新，不把既有kernel缺陷归因为概率所有权改动。


## 后续实现：packed 参数转换与输出恢复放在同一调用边界

来源：主会话 `01a1c90c-cc18-7063-8df2-30bdbddc6977` 第 7063 行（2026-11-12T11:07:47.722Z）提出把 `preparePackedMtpSampling` 移到 `sampler->forward` 前，与 restore 对称；第 7117 行（12:30:54.303Z）授权实施并检查相关格式。Turn 未核实。raw: `/home/baowending.bwd/.codex/sessions/2026/11/11/rollout-2026-11-11T13-20-21-01a1c90c-cc18-7063-8df2-30bdbddc6977.jsonl`。完整用户消息、8个文件的修改前快照和裁决保存在 `/home/baowending.bwd/packed-sampling-work/packed-boundary-20261112/`。

这是本项目明确的结构要求，旧调用位置本身未被证明造成数值错误。此前已读 R-OWN-14/15，但检查停在后端分派与概率输出所有权，没有继续区分通用参数准备和 MTP 行布局转换；既有规则足够，不增加重复规则。当前 gather 只准备、上传并应用 mask，CUDA 分支仅一次 `prepareSamplerInputs`；executor 在 forward 前后按实际映射成对做 packed prepare/restore。history/draft 通过 MTP 专用结果传递，不进入通用 sampler 接口；RNG 仍先按 dense 行预留。还发现 ngram 指针表的 CPU 填充和 H2D 藏在 packed helper 中，改为由既有 gather kernel 写入，减少一次上传且不增加 launch。相关局部变量明确正反映射和行数，删除未使用的 kernel 参数、include 与多余 move，只整理本次链路。

最终补丁 `8ba80b4afe078c3c92922636ad4fcf3e485c751d3534ea028597708d279af2f2` 实跑243项相关UT通过，含host/device draft、dense/sparse/identity布局、mask、history、三轮RNG与ngram指针及数值对照；24组kernel边界计时完成。计时在共享GPU上执行，不代表模型端到端；完整ROCm和模型smoke未运行。证据为上述目录的 `verification.json` 和 `performance.json`。用户明确要求GLM留在后台、后续显式回调，因此本轮没有等待或采纳其建议，也没有发起新的模型审查。代码未提交。


## 后续核查：准备过的采样分组不应在执行阶段重建

来源：主会话 `01a1c90c-cc18-7063-8df2-30bdbddc6977`，2026-11-13T08:51:06.690Z，Turn 未核实。用户指出 `samplePreparedGroups` 不应另传 token_ids，执行应直接遍历 group，并询问整批 token 输出复用 history 的原因。raw: `/home/baowending.bwd/.codex/sessions/2026/11/11/rollout-2026-11-11T13-20-21-01a1c90c-cc18-7063-8df2-30bdbddc6977.jsonl` 第 9373 行。

本轮读取 R-OWN-04/05、R-MIN-07。源码核实 groups 只覆盖单 beam，执行阶段又扫描全部 beam 数组并重新切片，同一 token view 还从独立参数覆盖 GreedyParams。准备责任只迁了一半，已有规则足够，属于落实不完整；不新增重复规则。整批输出 alias history 用于保留原地写最后一列的零复制路径，并非无意义初始化，混合 beam 行数变化仍需独立输出。后续应一次准备两类 group，统一绑定输入/输出 view，执行阶段只遍历 group；不能为去掉一个形参引入整批 cat/copy 或丢掉 beam 路径。本轮仅核查，未改生产代码、未运行测试；证据 `/home/baowending.bwd/packed-sampling-work/unified-sampler-20261113/feedback-sampling-groups.json`。

上述采样分组方案在同会话用户「嗯，这里你也改一下吧」授权后实施。仅修改 `Sampler.cc` 与 `SamplerTest.cc`：局部 group 持有输入/输出行区间及 GreedyParams/BeamSearchParams，执行改为 for-group，独立输入 token_ids 参数删除，整批 token 输出仍由 forward 复用或分配；未引入 history cat/copy 或新 kernel。CUDA 编译通过，9 个相关 UT 目标共 425 项通过，另 2 个默认禁用 benchmark；包含不变 beam 宽度的原地存储复用、混合 1→2/2→1 独立输出、跨 group RNG 和 packed 三轮对照。源码与二进制记录见 `/home/baowending.bwd/packed-sampling-work/unified-sampler-20261113/sampling-groups/validation.json`。ROCm 按用户要求暂不测试，代码未提交。

## 从功能复盘提炼通用审查动作（2026-11-26）

用户在第 2923 行指出上一版前三条依赖本次任务，第 2959 行确认「前两条补到已有规则，后两条单独成卡」，并要求逐项检查 `if` 中上游已经排除或保证的条件。Turn 未核实。raw: `/home/baowending.bwd/.codex/sessions/2026/11/25/rollout-2026-11-25T16-24-02-01a211cd-fdf8-7252-bf92-8f096efabd7f.jsonl`。

旧提案把整机启动的具体方案写进了规则的适用前提。此次把案例留在卡内，把审查动作写进判据。R-OWN-14 增加删除可选功能的推演，R-MIN-07 追问撤掉机制后的可达失败，R-MIN-01 检查复合条件中每一项对分支选择的贡献。新增 R-REV-15 对照职责迁移的新旧入口，新增 R-TST-06 判断高成本用例的独有覆盖。此次关于 `if` 的意见是通用要求，实际正反例取自已有审查记录。当前材料可确认旧提案的问题，无法据此判断历史上每个 reviewer 是否读过相近规则。多模型首轮模板和主技能加载路由均按改动类型选卡。

本轮验证：用订单扣款迁移和网关回调改变账户状态的独立审查样例，复核者沿正常入口发现重复扣款，保留可能被回调改变的条件，并指出只比舍入值的沙箱测试漏掉了该故障。两个技能入口结构校验及 agent-review 的 28 个本地测试均通过。


## 通用规则清理

用户要求「如果背景合理，只是说明不通用太贴近具体项目的，就改一下；如果完全是根据具体项目来的，就直接删除」。见 `codex/01a211cd-fdf8-7252-bf92-8f096efabd7f`，2026-11-26T06:44:39Z，第 3314 行。raw: `/home/baowending.bwd/.codex/sessions/2026/11/25/rollout-2026-11-25T16-24-02-01a211cd-fdf8-7252-bf92-8f096efabd7f.jsonl`。

以下编号已从规则正文和索引删除，保留编号供历史反馈回查。

| 原编号 | 原规定及处理 |
|---|---|
| R-STA-04、R-STA-06 | 删除统一按 token 加权和能力缺失一律给零的规定。聚合单位与权重归 R-STA-11，缺失值与观测值的语义归 R-STA-05。 |
| R-STA-07、R-STA-09、R-STA-10 | 移除特定统计方案、集合通信时机和后端计数接口的独立要求。状态读写周期由 R-STA-03 判断，新增机制的必要性由 R-MIN-07 判断。 |
| R-CFG-04 | 删除关于构建期开关和参数一律追加的组合规定。默认行为归 R-CFG-03，旧调用兼容性归 R-OWN-13。 |
| R-WRK-04、R-WRK-05、R-WRK-06、R-WRK-07 | 移除上游实现移植策略、质疑或叫停后的回滚、指定 Git 操作和预先提交方案清单的工作方式。原假设被证伪后重查修复范围的案例归 R-WRK-02。 |

复核时用了三个跨项目例子。租户 A 的请求成功 99/100，租户 B 成功 0/1，按租户等权得到 49.5%，按请求等权得到 99/101，两者各有适用的指标定义。线程在持锁区域调用会释放并重新获取锁的条件变量等待，可以由另一线程取得锁并通知。测试把固定顺序断言改为多重集相等时，若接口允许任意顺序，重复项和丢项仍受约束。三例分别对应 R-STA-11、R-STA-12 和 R-TST-01。
