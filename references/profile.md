# 配置与离线工具

`scripts/profile_tools.py` 只做本地 JSON 校验和标题格式化，不调用网络、应用或浏览器，不改会话、不创建任务、不写个人状态。它不能判断时间来源真假、主题、授权证据或运行状态，校验通过绝不等于可直接执行。

使用本机现有 Python 3.9+（需要标准 `zoneinfo` 可用；Windows 未带时区数据时报告缺依赖，不能偷换固定偏移）。无合适运行时仍可遵循文档手动执行，不能为辅助脚本全局安装环境。

```text
python scripts/profile_tools.py draft
python scripts/profile_tools.py validate <profile.json> --allow-draft
python scripts/profile_tools.py validate <profile.json>
python scripts/profile_tools.py title <profile.json> --created-at 1792575487 --unit seconds --category 咨询 --topic 奶粉真伪与渠道核验
python scripts/profile_tools.py locate
```

时间示例是离线演示，不作为任何真实目标的日期。数值字段单位必须明确选 seconds 或 milliseconds；ISO 字符串须带时区。禁止通过猜测单位让错误日期通过。

## 配置字段

| 字段 | 含义 |
|---|---|
| `schemaVersion` / `profileId` | 当前为 1；每位用户／独立设置一个新 ID |
| `setupStatus` | `draft` 或用户已确认的 `confirmed`；安装时保持 draft |
| `platforms` | 本人选择 `codex`、`chatgpt_web` 中的一项或两项 |
| `timezone` | 本人确认的 IANA 时区，不从作者时区继承 |
| `naming.format` | `{date} \| {category} \| {topic}`、`{category} \| {topic}`、`{date} \| {topic}` 之一 |
| `naming.dateFormat` | `%y%m%d`；真实 createdAt 的本地日期 |
| `naming.categories` | 用户确认的 `{name, description}` 列表，无固定数量；不显示分类的方案可留空 |
| `authorization` | `rename`、`unknownOriginFirstRename`、`allowNaturalOrderChanges` 与可追溯 `evidence`；默认三项 false |
| `scope.mode` | `new_only`、`approved_history_and_new`、`explicit_ids`；后两者需 `historyAuthorizationFile`，引用实际独立清单 |
| `schedule.kind` | `manual`、`daily`、`weekdays`、`weekly`、`custom` |
| `schedule.times` / `days` | 本地 HH:MM 列表；星期用 MO/TU/WE/TH/FR/SA/SU，weekly 必填 |
| `schedule.confirmed` / `requestedText` | 用户是否明确选定安排、原始可读要求；custom 必须保留具体要求 |
| `schedule.automationId` | 宿主实际返回的现有／新任务 ID，不能先编造；manual 为空 |
| `storage.stateDirectory` | 用户本机数据目录，若为相对路径则相对 profile 文件所在目录解析 |
| `legacyAdapter`（可选） | 已有任务的规则、状态、授权与历史日志路径；详见 existing-installation.md |

`active-profile.json` 格式为 `{"profilePath":"用户自己的绝对配置路径"}`。先保存和校验个人配置，再原子写登记文件；已有登记先读后决定是否使用，不覆盖其他配置。绝对路径只存在安装者自己的数据中。

## 版本与分发

当前维护版：`1.0.0+20261023.1`。直接修改基线：`1.0.0+20261022.1`。本次补充 GitHub 使用说明和用户授权的效果截图，同步版本元数据；执行流程与脚本执行逻辑保持不变。旧命名流程的 1.2 是设计来源，不是本 Skill 的前一版本。

安装包包含 `conversation-title-manager/` 内的 SKILL.md、agents 元数据、references、离线脚本，以及 README 和获用户授权的展示截图。除明确用于展示的截图外，不含个人配置、扫描结果、执行日志、账号或原作者基线。离线助手不继承任何已授权历史范围。更新时保留个人数据，先核对当前维护版本，禁止用旧包覆盖较新本地修改。

接收者解压后，将完整 `conversation-title-manager` 文件夹放入其 Codex 技能目录（通常 `$CODEX_HOME/skills`，未设置时 `~/.codex/skills`），再调用 `$conversation-title-manager`。若技能列表尚未发现，先核对安装路径与该宿主当前的技能发现方式；可直接让 Codex 读取该目录的 SKILL.md，不承诺所有宿主都支持即时刷新。安装时没有个人登记文件，首次会进入扫描与设置流程。
