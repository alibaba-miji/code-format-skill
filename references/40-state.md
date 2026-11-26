# 40 · 状态、缓冲与指标（R-STA）

> 改动涉及可变状态、异步执行或指标采集时，沿实际的读写和消费路径选读对应规则。

## R-STA-01 同一份统计由谁写入、结算和重置

- **内容**：跟一条观测从产生走到结算，确认它归属哪个对象、哪个统计周期。多个入口操作同一份状态时，核对谁提交、谁重置，以及提前返回对下一次采样的影响。
- **为什么**：两个组件分别结束同一轮统计，可能重复提交。两个独立对象共用一个窗口，也可能把各自的观测混在一起。
- **坏例**：
```cpp
static ExpertLoadMonitor g_monitor;  // 两个模型各自上报，共用的窗口里却混有对方的数据
```
- **好例**：
```cpp
class PyWrappedModel {
  ExpertBalancer expert_balancer_;   // 每个模型独立结算自己的窗口
};
```
- **判定**：取两个会交错运行的对象，或同一对象连续两个周期，逐笔追踪谁写了哪些值、最终会提交几次。指出产生漏计、重复或串数据的具体调用顺序。
- **例外**：各线程写各自分片、结算时统一归并也是有效的所有权划分。指标本来就描述全局总量时，可以共享计数器。
- **证据**：
  - `codex/2026-10-16T14-13-13` Turn 6：「我觉得应该每轮无脑 record…然后固定 step 汇总并提交；考虑下存储是不是用固定大小窗口（step）的 gpu buffer」｜raw: `/home/baowending.bwd/.codex/sessions/2026/10/16/rollout-2026-10-16T14-13-13-01a14357-d9f8-7643-9995-387cb01f0c18.jsonl`
  - `dsh/session-761ecd9b` Turn 36：「直接改成在框架里，每次 record 后清理一次吧，别再模型里感知这个逻辑了」｜raw: `/home/baowending.bwd/.dsh/sessions/--home-baowending.bwd-RTP-LLM-github-opensource--/session-761ecd9b-2f24-435e-8b68-2622832bea89/session.v4.jsonl.zstd`
  - `codex/2026-10-21T15-02-42` Turn 3：「用不同的 eplb_balancer，并且 eplb_balancer 绑定 pywrapped model，这样大小模型不会相互感知」｜raw: `/home/baowending.bwd/.codex/sessions/2026/10/21/rollout-2026-10-21T15-02-42-01a15d44-f514-7e61-8003-9d25a99ad946.jsonl`

## R-STA-02 延后执行的操作仍能使用先前绑定的资源

- **内容**：接口会保留引用、地址或句柄供稍后执行时，核对绑定对象的寿命，以及更新或重新绑定如何生效。对捕获设备地址的图，要检查重放时实际访问哪块存储。
- **为什么**：替换调用方的字段只会改变该字段的指向，已经捕获的操作可能继续读写旧对象。两块存储的形状和值都相同时，单次调用很难暴露问题。
- **坏例**：
```python
# 图已捕获 self.counts 的原地址；替换字段后，读者与图各用一块存储
self.counts = torch.zeros_like(self.counts)
graph.replay()
read_counts(self.counts)
```
- **好例**：
```python
# capture 时绑定到当前 bucket 的 slice，沿用这块存储直到该图停止重放
counts = self.counts[bucket]
counts.zero_()
graph.replay()
read_counts(counts)
```
- **判定**：在绑定和执行之间模拟一次替换、释放或扩容，分别指出生产者和消费者此后引用的对象。用实际 API 对引用和复制的约定来判断。
- **例外**：运行时支持安全更新绑定或重新捕获时，可以更换存储。按值复制的输入以及没有被捕获的临时缓冲按各自的生命周期处理。
- **证据**：
  - `codex/2026-10-16T14-40-50` Turn 1：「我希望 decode+cudagraph 情况下，这个 tensor 不是临时申请的，就是 cuda graph capture 时候按最大+slice」｜raw: `/home/baowending.bwd/.codex/sessions/2026/10/16/rollout-2026-10-16T14-40-50-01a14371-2226-7e70-ae9e-d7fd52f24658.jsonl`
  - `claude/da5780f8` Turn 1：「Counts graph address must remain fixed; checkExpertTokenCountsStable becomes the generic checkGraphInputStable.」｜raw: `/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/da5780f8-d4c1-4cc8-90e2-2afa4fd9afc2.jsonl`

## R-STA-03 复用缓冲时核对初始化、有效范围和累加周期

- **内容**：修改清零、覆盖写或累加的位置时，追到下一位读者。确认它读到的每个位置都有本次有效值，需要累加的部分从约定的初值开始，期间没有被提前重置。
- **为什么**：稀疏写入会留下上一次的非零值。在一次统计还没结束时清零，则会丢失前半段已经累加的数据。
- **坏例**：
```cpp
// counts 仍保留上一轮结果。本轮直接累加，把上一轮也算进来。
atomicAdd(&counts[expert], 1);
```
- **好例**：
```cpp
// 消费者只读这一轮的有效区，每个位置都被覆盖，包括值为零的位置。
for (int e = 0; e < local_experts; ++e) counts[e] = hist[e];
```
- **判定**：用前后两轮不同的写入范围检查残留，再用同一轮分两次写入检查是否漏加。把有效长度和每个读点对上。
- **例外**：有效位或代际标记能让读者识别旧数据，也可以省去整块清零。如果定义的就是跨调用累加，重置点取决于该统计周期。
- **证据**：
  - `codex/2026-10-16T14-40-38` Turn 1：「不用清空吧？下一轮写的时候反正会覆盖的」｜raw: `/home/baowending.bwd/.codex/sessions/2026/10/16/rollout-2026-10-16T14-40-38-01a14370-f477-7062-a847-0f77cc9ebc1c.jsonl`
  - `codex/2026-10-16T12-03-25` Turn 36：「不用清空吧？下一轮写的时候反正会覆盖的」｜raw: `/home/baowending.bwd/.codex/sessions/2026/10/16/rollout-2026-10-16T12-03-25-01a142e1-03e2-7c80-91f7-a6ccae9f6a25.jsonl`
  - `dsh/session-761ecd9b` Turn 34：「megamoe 有个参数 cumulative_local_expert_recv_stats，这样就不需要额外统计了，但是这个是累加的（chunk 切分 prefill），所以一开始一定要清空吧」｜raw: `/home/baowending.bwd/.dsh/sessions/--home-baowending.bwd-RTP-LLM-github-opensource--/session-761ecd9b-2f24-435e-8b68-2622832bea89/session.v4.jsonl.zstd`

## R-STA-05 指标聚合时区分缺失、展示占位值和真实的零

- **内容**：核对数据源能区分哪些情况，以及指标对它们各自的定义。某个数如果只在没有观测时用于展示，就不能无意中充当有效样本。同一个数如果代表真实观测，则按指标定义参与计算。
- **为什么**：缺失值被当作零会压低均值，缺失值被当作满分又会抬高均值。把真实的零过滤掉，同样会扭曲结果。
- **坏例**：
```python
# 例：要统计有负载层的平均均衡度，零负载层的展示默认值却是 1。
mean_balance = mean(layer.moe_lb for layer in layers)
```
- **好例**：
```python
observed = [layer.moe_lb for layer in layers if layer.total_activations > 0]
mean_balance = mean(observed) if observed else no_data_display_value
```
- **判定**：取一个有效的零值和一个缺测样本，算出预期的样本数、分子和分母，再与实现比较。如果消费方还要区分能力不可用与本周期没有事件，追查这种区别在哪一步可能丢失。
- **例外**：例如完整采集期间记录到零次失败，这个零可以是真实计数。产品定义明确要求填补缺测值时，核对使用的填补值和适用范围。
- **证据**：
  - `claude/93fd6fc1` Turn 1：「A zero-load layer's default 1 must never enter a mixed aggregate numerator/denominator.」｜raw: `/home/baowending.bwd/.claude/projects/-home-baowending-bwd-RTP-LLM-github-opensource/93fd6fc1-7420-4100-bafd-be1b633a6081.jsonl`
  - `codex/2026-10-21T15-02-42` Turn 3：「supports_expert_load_monitor 不应该在 python 层感知到，不支持就汇报 0 就行了」；Turn 4：「计数为 0，moe_lb 也报 0」｜raw: `/home/baowending.bwd/.codex/sessions/2026/10/21/rollout-2026-10-21T15-02-42-01a15d44-f514-7e61-8003-9d25a99ad946.jsonl`

## R-STA-08 核对异步热路径上新增等待的频率和依赖

- **内容**：在依靠重叠执行来满足吞吐或延迟目标的路径里，检查新增的取值、日志、条件判断有没有迫使调用方等待尚未完成的工作。沿后续代码找出第一次确实需要该结果的位置。
- **为什么**：从设备读一个标量也可能要等前面整段队列完成。代价取决于等待的位置和频率，标量本身的大小解释不了这个代价。
- **坏例**：
```cpp
// 每轮为了决定是否清零，先等设备返回元素个数。
if (counts.count_nonzero().item<int64_t>() != 0) counts.zero_();
```
- **好例**：
```cpp
counts.zero_();     // 本例在当前设备流上清零，后续工作由同一条流排序。
```
- **判定**：指出哪个调用引入等待、原来哪些工作可以重叠，以及这段路径多久执行一次。结论涉及延迟或吞吐损失时，用时间线或测量确认其影响。
- **例外**：后续动作依赖返回值，或协议把这里定义为完成边界时，等待有实际作用。
- **证据**：
  - `dsh/session-761ecd9b` Turn 36：「tensor 很小清理不花费时间（别 host 同步就行）」｜raw: `/home/baowending.bwd/.dsh/sessions/--home-baowending.bwd-RTP-LLM-github-opensource--/session-761ecd9b-2f24-435e-8b68-2622832bea89/session.v4.jsonl.zstd`

## R-STA-11 指标的观测对象、统计单位和聚合方法一致

- **内容**：从指标消费者的问题出发，写清一个样本代表什么，检查采样点、去重和权重。按请求、按用户或按工作量各算一次平均，回答的是不同的问题。计时同样要核对起止点所覆盖的工作。
- **为什么**：以逻辑路由预测实际负载会漏掉转发，平均各批次比率也可能让小批次和大批次的影响失衡。这些错误通常仍会给出看似正常的数值。
- **坏例**：
```python
# 目标是按处理的 token 衡量均衡度，却让两步权重相同。
balance = (0.9 + 0.2) / 2  # 两步各处理 128 个和 1 个 token，算出 0.55
```
- **好例**：
```python
balance = (128 * 0.9 + 1 * 0.2) / 129  # 同一案例按 token 加权，约为 0.895
```
- **判定**：选两组大小相差明显的样本手算结果。再沿一条可能重试、转发或并行执行的实际路径，核对有没有漏计、重复计数或提前结束计时。
- **例外**：指标定义为每用户或每批次等权时，简单平均正好符合要求。容量预测可以使用逻辑对象，实测负载则需要能反映实际执行的观测点。
- **证据**：
  - `remote106/claude/2d8f65f8` Turn 11：「统计对象必须是实际执行的 physical expert assignments，不能逻辑 expert 均分假装真实 GPU 负载」｜raw: `11.161.48.106:/home/baowending.bwd/.claude/projects/-data0-baowending-bwd-new-RTP-LLM-github-opensource/2d8f65f8-3028-4adc-8a2d-5a2aa79d2fe7.jsonl`
  - `remote106/codex/2026-10-13T18-44-50` Turn 24：「不用管 token kind，就算是 padding token 也是真实的参与 moe 计算了」「不用管 prefill/decode，我们只是计算每个 expert 激活量」｜raw: `11.161.48.106:/home/baowending.bwd/.codex/sessions/2026/10/13/rollout-2026-10-13T18-44-50-01a134dd-731c-7da0-ac30-5996fba028a8.jsonl`
  - `remote106/codex/2026-10-21T15-02-42` Turn 3：「在 c++ 层应该是大模型和小模型都汇报，用 model_type/model_id 啥的区分下就行」｜raw: `/home/baowending.bwd/.codex/sessions/2026/10/21/rollout-2026-10-21T15-02-42-01a15d44-f514-7e61-8003-9d25a99ad946.jsonl`
  - `codex/2026-10-16T14-40-50` Turn 2：「第 i 个 step 不均衡度 mean/max 是 0.9，跑了 128 个 token，另外 i+1 是 0.2，但是只有 1 个 token，那么汇总…(0.9+0.2)/2 就会特别小」｜raw: `/home/baowending.bwd/.codex/sessions/2026/10/16/rollout-2026-10-16T14-40-50-01a14371-2226-7e70-ae9e-d7fd52f24658.jsonl`
  - xgrammar 的整批耗时案例区分了各 worker 耗时之和与调用方实际等待的时间。见[已核对的原话和代码](90-feedback.md#已核对案例xgrammar-超时状态与批次耗时)。

## R-STA-12 核对持锁等待的依赖和解锁后对象的寿命

- **内容**：临界区里出现等待、回调或外部调用时，追查完成方是否也要拿这把锁，以及其他使用者是否需要在等待期间推进。把操作移到锁外时，同时核对对象的寿命和状态变更权限。
- **为什么**：在锁内等待另一个需要同一把锁的任务会死锁。只把等待挪出去，又可能让多个线程同时回收同一个对象。
- **坏例**：
```cpp
std::lock_guard<std::mutex> lk(mu_);
for (auto& n : nodes_) {
  cudaStreamSynchronize(n->stream);  // 其他流共用 mu_，等待期间也无法取得它
  if (n->state == DONE) reclaim(n);
}
```
- **好例**：
```cpp
std::vector<std::shared_ptr<Node>> claimed;
{
  std::lock_guard<std::mutex> lk(mu_);
  for (auto it = nodes_.begin(); it != nodes_.end();) {
    if ((*it)->state == DONE) {
      claimed.push_back(*it);        // 保活到锁外的回收结束。
      it = nodes_.erase(it);         // 从候选集合移除，其他回收者不能再次认领。
    } else {
      ++it;
    }
  }
}
for (auto& n : claimed) {
  cudaStreamSynchronize(n->stream);
  release_resources(n);
}
```
- **判定**：列出等待方、完成方和它们要获取的锁，再让另一线程在解锁后删除或再次认领该对象。分别验证资源仍然有效，且操作执行的次数符合协议。
- **例外**：条件变量等待会原子地释放锁并在返回时重新取得它。某些操作依赖锁内的原子性，应结合实际锁语义和竞争情况判断。
- **证据**：
  - `remote106/codex/2026-10-08T12-07-38` Turn 4（经 agent 转述）：「在服务锁内选择并标记 slot，退出服务锁后执行 copy；未出现服务锁持有期间等待 GPU 的全局串行化」｜raw: `11.161.48.106:/home/baowending.bwd/.codex/archived_sessions/rollout-2026-10-08T12-07-38-01a119b2-00da-7910-b7aa-6c661c471980.jsonl`
  - `remote106/codex/2026-10-15T11-25-23` Turn 1（经 agent 转述）：「一个节点调用 rundroptask 清理掉另外一个节点」时的批内悬空防护｜raw: `11.161.48.106:/home/baowending.bwd/.codex/sessions/2026/10/15/rollout-2026-10-15T11-25-23-01a13d97-d5d3-7031-be45-3bc0c6670aba.jsonl`
