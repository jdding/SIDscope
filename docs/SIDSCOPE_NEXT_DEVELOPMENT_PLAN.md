# SIDScope 本地后续开发计划

## 当前状态（2026-09-09，覆盖下方历史记录）

- N02-N08 的已批准工程范围均已开发、测试并写入验收台账。
- N08 严格止于两条路线各 100 episode：回传哈希、本地验证及各三次独立
  后处理重复均通过；不再扩到 1000，不重跑模型，不追加生产 SLO。
- N07 已实现显式 `ordered_prefix`、`parallel_positions`、`unordered_set`
  语义，区分 raw churn、item 增删和 common-item 结构变化；RPG 12,101 item
  与 PSID 17,396 item 的实际形状零变化控制通过，但不宣称真实 refresh 效应。
- Adapter SDK 已按选择稳定为 1.0.0，39-symbol curated facade 不扩张；机器
  surface、迁移、ADR、installed consumer 和 typed negative 已同步。
- `--require-engineering-ready` 通过；N01/F09 独立用户实际使用是唯一认证
  阻塞项。N09/N10 暂不排期，也不建设 hosted service 或训练框架。
- RC 前工程交付门禁已执行：Linux/Python 3.9-3.12 matrix、三 profile
  archive/smoke、regular install/G8、干净本地 commit 与 exact-source 回执。
  下一步只剩 F09；完成后以 RC 版本从新 commit 重跑同一门禁。推送、tag、
  GitHub Release 仍需单独明确授权。

## 已完成的 N07/N08 有界结论（2026-09-09）

N08 的正式适用范围固定为当前两条冻结路线各 100 episode。RPG 三次本地
后处理 median 50.2044 s、peak RSS median 1,791,819,776 bytes、输出 174,002
bytes；PSID 分别为 9.5620 s、1,048,821,760 bytes、261,110 bytes。数值不是
任意机器、负载或生产环境保证。

N07 复用现有 D6/evaluation 内核但不修改其历史行为。RPG 的 32 位向量按独立
位置码本处理，只比较 full code；PSID 的 3 位 SID 才计算 prefix。相同 mapping
控制全部为零变化，证明实现不会凭空制造 churn；真正 before/after refresh 仍需
未来用户提供两份身份一致的快照，届时无需扩展本轮产品范围。

## 2026-09-08 历史推进记录（非当前状态）

日期：2026-09-08。保持 `1.7.0.dev0`；不激活 1.8，不以 2.0 容纳未完成工作。
最新：ADR-0020 已将两条真实观察接入 canonical 身份、SDK TraceEnvelope、诊断
EvidenceBundle 准入及同输入比较，并增加原始输入重建复核。N03 技术接入完成；
F09 的实际独立用户使用仍未完成，不用自动化代替。新 checkpoint 绑定区分最佳
与最终训练进度（PSID 9372/10000，RPG 10807/12827），不宣称训练复算。
以下观察-only 状态为上一批历史记录；下一技术项按 N05 → N04 → N08 推进。
当前批准顺序：先推进第 1、2 项，再依次完成第 3、4、5 项；成本测量贯穿。
第 2 项新增 mapping preflight、条件 D3/D4 与 train-only 保护；第 1 项完成通用
producer 编排及两条各 5 episode 的真实 CPU 观察，但 RPG/PSID 原生到 canonical
导出和 EvidenceBundle 适配仍未完成。
已在复旦定位候选工作目录，两份 checkpoint 实际 digest 与冻结记录一致；
RPG model.py digest 也已匹配。尚非全部资产身份核验或真实运行验收。
通用合成编排测试不是实际接入，详见 ADR-0019。输入政策上一批结果保持不变。

本轮新增纯数据 native rank projection：保留原始排名槽位，显式绑定 target
selection 和后续用户聚类身份，调用旧 verifier 和指标内核；无标签不计算指标。
先前观察器操作被安全审查拒绝；用户后续明确批准后，已在复旦新临时目录完成
两条 CPU 观察。密钥仅在原地使用，原资产未改写；失败观察记录保留，不覆盖。
本地验收完成真实 12,101 / 17,396 item 全 catalog、67,089 / 42,756 split joins，
每条选中 5 个真实目标并记录实际 forward/NFE。缺 category/capacity 等输入仍
明确 unavailable。同文件比较仅证明重算一致性，不是多 run/seed 比较。
F09/N03 尚未完成；本地投影测试不是完整 canonical/bundle 接入验收。

## 当时的状态纠正（历史）

F09 / N03 为 partial：两个已有真实导出文件的 inspection 只覆盖原始验收的一部分。
不能据此宣称两条真实 producer 链路或独立用户验收已闭环。
N08 为 partial：已有 10k/100k/1M 合成规模实测，尚非真实输入/SLO/NFE 验收。
历史结果保留；没有实际运行证据的项目不得由文档、哈希或签收替代。

## 优先级与执行顺序

| 顺序 | 交付目标 | 严格退出条件 |
| --- | --- | --- |
| 1：F09、N01/N03 | 两个已有不同 native family 的真实端到端 golden path。一个本地 run spec 从 producer 导出，经验证、诊断到 immutable bundle 和比较；先复用 RPG/PSID 接口，不堆新算法名字。 | 两条实际 producer 链路都执行；无需改 core、手拼内部 JSON 或补哈希；协议和原生语义不变；缺失标签/事实明确 unavailable。故意篡改、缺输入及协议不兼容负例拒绝。F09 另需实际独立用户操作记录，自动化不能冒充，且不要求签字。 |
| 2：N06 | Mapping-first 完整体检。加入 catalog、split、target 与 SID 的一致性 join，按可用输入启用已有 D3/D4，形成统一 preflight。 | 真实输入能定位越界 item、缺失/重复映射和 split 错配；缺少依赖时精确列出未执行项；CLI/API 一致，不自动修 SID。 |
| 3：N05 | 多 run/seed 回归比较。冻结评估协议，明确配对单位、用户聚类、效应量、区间和可配置退化预算。 | 用已知结果数据校验统计量与覆盖行为；不同 cohort/协议拒绝合并；seed 与用户采样不混同；重复记录、不足样本和缺失 run 有 typed 结果。 |
| 4：N04 | 可行动的诊断和静态离线报告。受影响 slice、脱敏案例、证据位置、下一步检查；严格区分观察、假设、已证实原因。 | 至少三个预设退化能指回具体证据；离线可读，缺失信息不推断因果；隐私检查、差异和 supersession 可追溯。 |
| 5：N08 | 在上述真实工作流上形成成本/规模验收。阶段耗时、峰值内存、输出体积及原生 trace 实际可用的 NFE。 | 冻结代表性负载并重复测量；公布机器和适用范围；NFE 缺失则不报告；只有实测内存/吞吐不满足使用需求才实施分块或 streaming，并验证数值、顺序和 evidence identity 等价。 |

N08 的测量伴随各阶段，不必等第五项才测；第五项完成真实规模能力声明。
当前百万行结果表明暂不需要为此次取消限制另建服务或全面 streaming；评估报告
保留完整输入，输出约 266 MB、进程峰值约 3.72 GiB，是下一阶段应关注的复制成本。
这些数字是单次合成实测，不能替代真实用户负载或分位延迟。

## 每批次统一完成定义

1. SPEC / 验收例先对齐原始需求；若缩减范围，明确保留未完成项。
2. 实现、typed negatives、CLI/API parity 和必要 ADR/manifest/文档同步。
3. CPU 全套测试、resource/profile verifiers、独立 installed consumers 与
   新的 exact-source local release record 通过；原 evidence 不重写。
4. 需求表分别记录 implemented、verified、user_accepted、delivery_ready，
   缺失一层不以另一层 PASS 代替。工程交付记录不等于 2.0 certification。
5. 上述批准范围的技术项和实际使用条件齐备后再做 certification-readiness audit；
   仍有缺口就继续在适当本地 1.x 闭环。推送、tag、公开发布另需明确授权。

本地 CPU 工作无需训练。只有必要且可复算的训练事实才考虑既定复旦集群流程；
不必要或无法复算的事实保持未验证，不引入签收、虚构标签或无关 GPU 作业。
