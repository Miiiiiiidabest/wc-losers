# ⚽ WC Losers — Polymarket 世界杯「连输钱包」追踪器

追踪 Polymarket 上 2026 世界杯比赛盘里**一直连输的钱包**：谁连输最多场、谁胜率最低、谁现在还在连败中、他们都押错了什么。数据每天自动更新。

**[English summary below ⬇](#english)**

## 🌍 在线使用（无需安装）

| 页面 | 链接 | 说明 |
|---|---|---|
| **连输总榜** | [miiiiiiidabest.github.io/wc-losers](https://miiiiiiidabest.github.io/wc-losers/) | 三个排行榜：最长连输 / 最低胜率 / 当前连输中 |
| **单场拆解工具** | [/match.html](https://miiiiiiidabest.github.io/wc-losers/match.html) | 选任意一场比赛（含进行中的），实时看连输钱包押了哪边 |

## 它能告诉你什么

- 🔥 哪些钱包**连输 20+ 场、胜率 0%、至今还在连败**（点地址可跳 Polymarket 主页核对）
- 💎 区分**从头拿到尾的纯持有型**（真·判断错误）和**波段交易型**（含交易失误的噪音）
- 🎯 每个钱包**最常押错的选项**，以及全体输家最爱扎堆的方向
- ⚡ 比赛进行中，实时查看连败大军正押在哪边

## 📊 基于 2.6 万个钱包的一些发现

把下注 ≥5 场的钱包按胜率分成「输家组」（≤25%）和「赢家组」（≥60%）对比：

| 行为 | 输家组 | 赢家组 |
|---|---|---|
| 押注里平局的占比 | 24.8% | 11.6% |
| 押平局的命中率 | **14%**（低于 27% 的随机基准！） | **61%** |
| 押中时的平均买入价 | $0.46（爱买冷门） | $0.76（爱买热门） |
| 输一场后的下注变化 | 加注 1.10×（追损） | 减注 0.92× |
| 总回报率 | **−59.5%** | 仅 +1.3% |

一句话：**输家输在"买便宜的梦"——高赔率平局、冷门、输了加倍；赢家赢在"收无聊的钱"。** 另外：每场比赛里，正处于 ≥5 连败的钱包最集中押的方向，85 场里输了 70 场（82%）。

## 数据口径

- 只统计**比赛结果盘**（每场 = 主胜/平/客胜三个二元市场），不含角球、比分、球员道具等子盘
- 胜负判定：已结算市场 `outcomePrices` 中为 `"1"` 的一侧
- 单场输赢：该钱包在这场三个盘的**净盈亏**（买卖现金流 + 结算赔付），净亏记一次输；忽略 <$1 的零星仓位
- 连输 = 按比赛日期排序后的连续净亏场数
- 💎 纯持有 = 卖出股数 ≤ 买入股数的 10%（其余视为波段/做市，其"输"含交易行为噪音）
- 数据源：Polymarket 公开 API（[Gamma](https://gamma-api.polymarket.com) 市场数据 + [Data API](https://data-api.polymarket.com) 成交/持仓）

**已知局限**：每个钱包的活动记录 API 上限约 2000 条，极高频钱包的早期记录可能缺失；单场拆解的实时模式只抓每盘最近约 2000 笔成交，是活跃钱包快照而非全量。

## 🔧 自己跑一遍

无第三方依赖，Python 3.9+ 标准库即可：

```bash
git clone https://github.com/Miiiiiiidabest/wc-losers.git
cd wc-losers/pipeline

python3 collect.py            # 1. 抓已结算比赛 + 从成交中发现活跃钱包（约10分钟）
python3 crawl.py              # 2. 逐钱包抓完整交易记录并分析（约1-2小时，可中断续跑）
python3 build_dashboard.py    # 3. 生成 dashboard.html（本地打开即用）
python3 build_match_tool.py   # 4. 生成 match_breakdown.html
```

每日自动刷新参考 `pipeline/refresh.sh`（macOS launchd 定时任务）。**注意**：脚本里的路径需改成你自己的；macOS 用户别把定时任务的工作目录放在 `~/Documents`（系统隐私保护会静默拦截后台任务，报 "Operation not permitted"）。

## 项目结构

```
index.html              # 连输总榜（生成产物，每日自动更新）
match.html              # 单场拆解工具（生成产物）
pipeline/
  collect.py            # 抓比赛列表 + 发现候选钱包
  crawl.py              # 逐钱包分析：盈亏、连输、胜率、押注方向、持有类型
  build_dashboard.py    # 生成总榜页面（full / share / site 三种模式）
  build_match_tool.py   # 生成单场拆解页面
  refresh.sh            # 每日全流程刷新 + 自动发布（launchd 调度）
```

## 免责声明

所有数据来自区块链和 Polymarket 公开 API，钱包地址本身即公开信息。本项目仅供数据研究与娱乐，**不构成任何投注建议**——事实上，如果这个项目说明了什么，那就是大多数人都在亏钱。

## License

[MIT](LICENSE)

---

## English

**WC Losers** tracks chronically losing wallets on Polymarket's 2026 World Cup match markets: longest losing streaks, lowest win rates, active streaks, and what they keep betting on. Live at [miiiiiiidabest.github.io/wc-losers](https://miiiiiiidabest.github.io/wc-losers/) (leaderboard) and [/match.html](https://miiiiiiidabest.github.io/wc-losers/match.html) (per-match breakdown, works on live games).

Method: only 3-way match-result markets (home/draw/away); a wallet "loses" a game when its net P&L (trade cash flow + settlement) is negative; streaks are consecutive losses by match date; 💎 marks buy-and-hold wallets (sold ≤10% of shares bought). Data from Polymarket's public Gamma & Data APIs; per-wallet activity capped at ~2000 records by the API.

Run it yourself — pure Python 3.9+ stdlib, no dependencies: see the four scripts under `pipeline/` (collect → crawl → build). Not betting advice; if anything, the data shows most people lose.
