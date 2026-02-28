很好 👍
这个 take-home 虽然重点在后端，但如果你做一个简单但专业的前端界面，会极大加分。

我给你写一份前端任务总结文档（可作为你开发 checklist）。

⸻

📄 前端任务总结（Tender Automation Demo UI）

🎯 前端目标

构建一个简洁、可演示、专业的 Web 界面，用于：1. 上传新 Tender Excel 文件 2. 查看处理进度 3. 查看每题生成结果 4. 查看风险标记 5. 查看最终 summary 6. 下载结果文件（JSON / Excel）

不需要做 Chat UI。
这是一个批处理结果展示系统。

⸻

一、前端核心页面结构

建议单页应用（React / Next.js 均可）。

⸻

页面 1：Tender Processing Dashboard

模块 1：历史库状态展示（可选加分）
• 显示：
• 历史条目数量
• domain 分布
• 上次更新时间

API:

GET /history/status

目的：展示你有长期 memory。

⸻

模块 2：上传区域

功能：
• 上传 Excel 文件
• 可选择：
• output format（json / excel）
• similarity threshold（可选高级选项）
• 点击 “Process”

API:

POST /tender/process

UX 建议：
• 文件拖拽上传
• 显示文件名
• 上传后显示 loading spinner

⸻

模块 3：Processing 状态区
• 显示：
• 当前状态（processing / completed / partial success）
• 总题数
• 已完成数
• 失败数

如果你做流式更新（可选加分）：
• 逐题进度条

⸻

模块 4：Question Result Table（核心展示区）

表格展示：

| Question | Domain | Alignment | Confidence | Risk | Status |

点击某一行可以展开：
• Original Question
• Generated Answer
• Historical Matches（展示相似度 + 来源）
• Risk Flags
• Error Message（如失败）

这块是你展示“企业级可审计 AI”的关键。

⸻

模块 5：Summary Panel

显示：
• Total questions
• Success count
• Failed count
• High-risk count
• Inconsistent count
• Overall status

可以做成：
• 统计卡片
• 或简单 summary box

⸻

模块 6：下载按钮
• Download JSON
• Download Excel

⸻

二、前端数据结构（与后端对齐）

你前端接收的 response 结构应该类似：

{
"session_id": "...",
"summary": { ... },
"results": [
{
"original_question": "...",
"generated_answer": "...",
"domain_tag": "...",
"confidence_level": 0.82,
"historical_alignment": "aligned",
"risk_flags": [],
"status": "success"
}
]
}

前端只做展示，不做业务逻辑。

⸻

三、前端必须体现的“评分点”

面试官会看：

1️⃣ 可解释性

是否能看到：
• 哪个历史回答被参考
• 相似度是多少
• 为什么被标记 risk

⸻

2️⃣ 风险可视化

建议：
• high_risk 用红色标
• inconsistent 用橙色
• aligned 用绿色

⸻

3️⃣ 失败隔离

某题失败时：
• 不影响其他题显示
• 单独标红
• 展示 error message

⸻

4️⃣ 专业感

不要太花哨。

建议：
• 简洁布局
• 明确分区
• 清晰 typography

这是企业系统，不是 marketing site。

⸻

四、前端技术建议

如果时间有限：
• React + Vite
• 或 Next.js（但不要 SSR 复杂化）
• Tailwind 简单样式即可

不需要：
• 复杂路由
• 认证系统
• 状态管理库（简单 useState 足够）

⸻

五、你可以选择两种复杂度

🎯 基础版（足够合格）
• 文件上传
• 结果表格
• summary
• 下载按钮

就可以。

⸻

🚀 加分版
• 逐题展开查看 retrieval hits
• 显示 similarity score
• 可筛选 risk / domain
• 可切换历史匹配路径展示

⸻

六、前端的定位

不要过度开发。

这个前端的作用是：

帮你展示“多 Agent 工作流结果是可解释、可审计、结构化的”。

不是：

设计一个 SaaS 产品 UI。

⸻

七、推荐前端页面结构示意

[ Header ]
Tender Response Automation

[ History Status Card ]

[ Upload Section ]

[ Processing Status ]

[ Results Table ]

[ Summary Section ]

[ Download Buttons ]

⸻

八、最终目标

你的前端应该让面试官在 30 秒内看懂：
• 系统是批处理 workflow
• 每题都有状态
• 有历史对齐
• 有风险控制
• 有 summary
• 可以下载结果

⸻

如果你愿意，我可以下一步：
• 帮你设计一个极简高质感的 UI 结构
• 或帮你写一个前端接口调用示例
• 或帮你写一个“演示脚本”（你给面试官 demo 时怎么讲）

你想往哪个方向走？
