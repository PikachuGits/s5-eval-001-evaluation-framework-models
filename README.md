# S5-EVAL-001 · 评测框架数据模型：评测集、用例、运行与结果表

ClawHunt 工单 **#1831** 交付物。本仓库包含 AI 辅助工具评测框架的 5 张核心表
（`eval_suite` / `eval_case` / `eval_run` / `eval_result` / `eval_baseline`）、
Alembic 迁移、180 天结果清理脚本、Pydantic schema、Mermaid ER 图与 pytest 测试。

- 数据库：PostgreSQL 16（本次实测 16.16）
- 公开仓库：<https://github.com/PikachuGits/s5-eval-001-evaluation-framework-models>
- 本次运行：**测试结果见 `evidence/test-results.txt`**（真实 PostgreSQL，`alembic check` 零漂移）
- 证据：`evidence/test-results.txt`、`evidence/migration-check.txt`

> **边界声明（先读）**
>
> 1. 本单只做**表模型 + 迁移 + schema + 清理脚本 + 约束测试**；不实现评测执行器、
>    判分模型、调度器或 FastAPI 路由，也不改工作台前端。
> 2. 所有测试数据均为虚构（`kqa.retrieval`、`CASE-001`、虚构问题与要点），
>    不含客户名称、真实会员企业或个人信息。
> 3. 不引入任何向境外发送数据的第三方 SDK。依赖其他工单的接口时按项目约定
>    用字段约定 / mock 先行；本单**无外部服务依赖**。
> 4. 本仓库产出的是代码与测试证据，不代表平台验收或结算。

---

## 1. 范围

| 做 | 不做 |
|---|---|
| 5 张表的 SQLAlchemy 2 模型、统一字段与软删除 | 评测执行器 / 判分模型实现 |
| Alembic 迁移（约束、复合外键、索引） | CI 触发、nightly 调度、重跑编排 |
| 180 天结果清理脚本（基线永久保留） | 对象存储、报表页面、前端图表 |
| Pydantic 创建/读取 schema 与字段校验 | FastAPI 路由、权限中间件 |
| pytest 约束测试（迁移往返、唯一键、复合外键、冻结时间清理） | 客户真实数据 / 真实模型联调 |
| README + Mermaid ER 图 | 部署流水线 |

依赖其他工单时按项目约定用接口/字段约定先行；本单没有外部服务依赖。

---

## 2. 快速开始

```bash
# 1) 准备一个 PostgreSQL 16 测试库（库名必须含 test，测试会重建 public schema）
createdb -h 127.0.0.1 -p 5432 clawhunt_1831_test

# 2) 安装依赖
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 3) 建表
export DATABASE_URL='postgresql+psycopg://USER:PASSWORD@127.0.0.1:5432/clawhunt_1831_test'
.venv/bin/alembic upgrade head

# 4) 全量测试
export TEST_DATABASE_URL="$DATABASE_URL"
EVIDENCE_OUT=evidence/test-results.txt ./scripts/test.sh

# 5) AC-1 证据：upgrade → downgrade → upgrade → alembic check
./scripts/migration-check.sh
```

可选 Docker 测试库：

```bash
docker compose -f docker-compose.test.yml up -d
export TEST_DATABASE_URL='postgresql+psycopg://clawhunt@127.0.0.1:55435/clawhunt_1831_test'
```

### 2.1 `0002` 迁移的存量数据前置条件

**新库 / 五张表为空时无需检查，直接 `alembic upgrade head` 即可。**

`0002_tenant_aware_fks` 是纯约束迁移，不搬运数据。如果从 `0001` 升级的库里
已经存在租户/站点字段不一致的关联记录，`ALTER TABLE ... ADD FOREIGN KEY`
会失败。升级前先在 `0001` 版本执行以下检查，**所有查询都必须返回 0 行**：

```sql
-- case / run 的 suite 必须同租户、同站点
SELECT 'eval_case' AS table_name, c.id
FROM eval_case c
JOIN eval_suite s ON s.id = c.suite_id
WHERE (c.org_id, c.site_id) <> (s.org_id, s.site_id);

SELECT 'eval_run' AS table_name, r.id
FROM eval_run r
JOIN eval_suite s ON s.id = r.suite_id
WHERE (r.org_id, r.site_id) <> (s.org_id, s.site_id);

-- result 的 run / case 必须同套件、同租户、同站点
SELECT 'eval_result' AS table_name, x.id
FROM eval_result x
JOIN eval_run r ON r.id = x.run_id
JOIN eval_case c ON c.id = x.case_id
WHERE x.suite_id <> r.suite_id
   OR x.suite_id <> c.suite_id
   OR (x.org_id, x.site_id) <> (r.org_id, r.site_id)
   OR (x.org_id, x.site_id) <> (c.org_id, c.site_id);

-- baseline 的 run / suite 必须同套件、同租户、同站点
SELECT 'eval_baseline' AS table_name, b.id
FROM eval_baseline b
JOIN eval_run r ON r.id = b.run_id
JOIN eval_suite s ON s.id = b.suite_id
WHERE b.suite_id <> r.suite_id
   OR (b.org_id, b.site_id) <> (r.org_id, r.site_id)
   OR (b.org_id, b.site_id) <> (s.org_id, s.site_id);
```

若有返回行，先按父行修正子行的 `org_id` / `site_id` / `suite_id`，或清理这批
测试/脏数据，再重跑检查；确认 0 行后再执行 `0002`。本单不提供自动数据修复，
避免在迁移里静默改写租户归属。

---

## 3. 表结构

所有业务表统一包含：

| 列 | 类型 | 空 | 默认 | 说明 |
|---|---|---|---|---|
| `id` | UUID | 否 | `gen_random_uuid()` | 主键 |
| `org_id` | UUID | 否 | — | 租户 |
| `site_id` | UUID | 否 | — | 站点 |
| `created_at` | TIMESTAMPTZ | 否 | `now()` | 创建时间 |
| `created_by` | UUID | 是 | — | 创建人 |
| `updated_at` | TIMESTAMPTZ | 否 | `now()` | 更新时间（应用层维护） |
| `deleted_at` | TIMESTAMPTZ | 是 | — | 软删除 |

金额字段不在本单范围内。`pass_rate`、`score_avg`、`score` 统一使用 0–100 口径。

### 3.1 `eval_suite`（评测集）

| 列 | 类型 | 空 | 默认 | 说明 |
|---|---|---|---|---|
| `suite_key` | VARCHAR(64) | 否 | — | 稳定标识，如 `kqa.retrieval`，正则 `^[a-z0-9][a-z0-9_.-]{1,63}$` |
| `tool` | VARCHAR(32) | 否 | — | `ops_assist` / `biz_ai` / `ip_content` / `intel_brief` / `doc_auto` / `staff_assistant` / `kqa` / `guardrail` |
| `version` | INTEGER | 否 | `1` | 版本号，≥ 1；改用例即升版本，不改历史 |
| `case_count` | INTEGER | 否 | `0` | 用例数缓存，≥ 0，由应用层维护 |
| `status` | VARCHAR(16) | 否 | `'draft'` | `draft` / `active` / `retired` |

约束与索引：

- `UNIQUE (org_id, site_id, suite_key, version)`：同一租户站点下同一版本唯一；
- `UNIQUE (id, org_id, site_id)`：供 case/run/baseline 的租户感知复合外键引用；
- `CHECK`：`tool`、`status`、`version >= 1`、`case_count >= 0`、`suite_key` 格式；
- `ix_eval_suite_tenant_status (org_id, site_id, status)`、`ix_eval_suite_tenant_tool (org_id, site_id, tool)`。

### 3.2 `eval_case`（评测用例）

| 列 | 类型 | 空 | 默认 | 说明 |
|---|---|---|---|---|
| `suite_id` | UUID | 否 | — | 租户感知复合 FK `(suite_id, org_id, site_id) → eval_suite(id, org_id, site_id)`，`ON DELETE RESTRICT` |
| `case_key` | VARCHAR(64) | 否 | — | 套件内稳定标识，如 `CASE-001` |
| `input` | JSONB | 否 | `'{}'` | 传给被测工具的输入，必须是 JSON 对象 |
| `context` | JSONB | 否 | `'{}'` | 上下文夹具，必须是 JSON 对象 |
| `expected_points` | JSONB | 否 | `'[]'` | 必须命中的要点，必须是 JSON 数组 |
| `forbidden_points` | JSONB | 否 | `'[]'` | 禁止命中/禁止出现的内容，必须是 JSON 数组 |
| `reference_output` | TEXT | 是 | — | 参考答案，可为空 |
| `tags` | TEXT[] | 否 | `'{}'` | 标签，去重后写入 |
| `difficulty` | VARCHAR(16) | 否 | `'medium'` | `easy` / `medium` / `hard` |
| `weight` | NUMERIC(6,3) | 否 | `1.000` | 套件内权重，> 0 |
| `review_state` | VARCHAR(16) | 否 | `'pending'` | `pending` / `approved` / `rejected` |

约束与索引：

- `UNIQUE (suite_id, case_key)`：同一套件内用例标识唯一；
- `UNIQUE (id, suite_id, org_id, site_id)`：供租户感知结果外键引用；
- `CHECK`：枚举、`weight > 0`、JSON 形状（`input`/`context` 为 object，两个 points 为 array）；
- `ix_eval_case_tenant_suite (org_id, site_id, suite_id)`、`ix_eval_case_suite_review (suite_id, review_state)`。

### 3.3 `eval_run`（评测运行）

| 列 | 类型 | 空 | 默认 | 说明 |
|---|---|---|---|---|
| `suite_id` | UUID | 否 | — | 租户感知复合 FK `(suite_id, org_id, site_id) → eval_suite(id, org_id, site_id)`，`ON DELETE RESTRICT` |
| `suite_version` | INTEGER | 否 | — | 运行所锁定的套件版本，≥ 1 |
| `target_tool` | VARCHAR(32) | 否 | — | 被测工具，取值同 `eval_suite.tool` |
| `target_prompt_version` | VARCHAR(64) | 是 | — | Prompt 版本 |
| `target_model` | VARCHAR(64) | 是 | — | 被测模型 |
| `trigger` | VARCHAR(16) | 否 | — | `ci_pr` / `nightly` / `manual` |
| `git_sha` | VARCHAR(64) | 是 | — | 小写十六进制 7–64 位 |
| `status` | VARCHAR(16) | 否 | `'queued'` | `queued` / `running` / `succeeded` / `failed` / `cancelled` |
| `pass_rate` | NUMERIC(5,2) | 是 | — | 通过率百分比 `[0,100]`，终态前为空 |
| `score_avg` | NUMERIC(6,3) | 是 | — | 平均分，0–100 口径，≥ 0 |
| `token_usage` | BIGINT | 否 | `0` | prompt + completion 总 token，≥ 0 |
| `started_at` | TIMESTAMPTZ | 否 | `now()` | 开始时间 |
| `finished_at` | TIMESTAMPTZ | 是 | — | 结束时间，不得早于 `started_at` |

约束与索引：

- `UNIQUE (id, suite_id, org_id, site_id)`：供 `eval_result` / `eval_baseline` 的租户感知外键引用；
- `CHECK`：`target_tool`、`trigger`、`status`、`suite_version`、`pass_rate` 区间、`score_avg`、`token_usage`、时间顺序、`git_sha` 格式；
- `ix_eval_run_suite_started (suite_id, started_at)`、`ix_eval_run_tenant_status (org_id, site_id, status)`。

### 3.4 `eval_result`（评测结果）

| 列 | 类型 | 空 | 默认 | 说明 |
|---|---|---|---|---|
| `run_id` | UUID | 否 | — | 租户感知复合 FK `(run_id, suite_id, org_id, site_id) → eval_run(id, suite_id, org_id, site_id)`，`ON DELETE CASCADE` |
| `case_id` | UUID | 否 | — | 租户感知复合 FK `(case_id, suite_id, org_id, site_id) → eval_case(id, suite_id, org_id, site_id)`，`ON DELETE RESTRICT` |
| `suite_id` | UUID | 否 | — | 必须同时匹配 run、case 及本行的 `org_id` / `site_id` |
| `output_text` | TEXT | 是 | — | 原始输出 |
| `output_json` | JSONB | 是 | — | 结构化输出，可为任意 JSON |
| `score` | NUMERIC(6,3) | 是 | — | 0–100；判分失败时为空 |
| `passed` | BOOLEAN | 是 | — | 通过/不通过；无法判定时为空 |
| `point_hits` | JSONB | 否 | `'[]'` | 命中的 expected points，JSON 数组 |
| `violations` | JSONB | 否 | `'[]'` | 违规项，JSON 数组 |
| `latency_ms` | INTEGER | 是 | — | 延迟毫秒，≥ 0 |
| `judge_trace` | JSONB | 否 | `'{}'` | 判分模型、rubric 版本与中间过程，JSON 对象 |
| `error` | TEXT | 是 | — | 执行错误信息 |

约束与索引：

- **`UNIQUE (run_id, case_id)`**：同一 run 对同一用例只能有一行结果（AC-2），
  PostgreSQL 自动建立同名唯一索引 `uq_eval_result_run_case`；
- 复合外键保证「结果不能引用别的套件/别的租户的用例」「run 删除时结果级联清理」「用例仍被结果引用时禁止硬删」；
- `ix_eval_result_tenant_run (org_id, site_id, run_id)`、`ix_eval_result_case (case_id)`。

### 3.5 `eval_baseline`（基线）

| 列 | 类型 | 空 | 默认 | 说明 |
|---|---|---|---|---|
| `suite_id` | UUID | 否 | — | 租户感知复合 FK `(suite_id, org_id, site_id) → eval_suite(id, org_id, site_id)`，`ON DELETE RESTRICT` |
| `run_id` | UUID | 否 | — | 租户感知复合 FK `(run_id, suite_id, org_id, site_id) → eval_run(id, suite_id, org_id, site_id)`，`ON DELETE RESTRICT` |
| `set_by` | UUID | 是 | — | 设置人 |
| `set_at` | TIMESTAMPTZ | 否 | `now()` | 设置时间 |
| `note` | TEXT | 是 | — | 备注 |

约束与索引：

- `UNIQUE (suite_id, run_id)`：同一次运行不能被同一套件重复登记为基线；
- 保留历史：一个套件可以有多条基线记录，最新一条即“当前基线”（按 `set_at`）；
- `ix_eval_baseline_suite_set_at (suite_id, set_at)`。

---

## 4. ER 图

```mermaid
erDiagram
    eval_suite ||--o{ eval_case : "contains"
    eval_suite ||--o{ eval_run : "executes"
    eval_suite ||--o{ eval_baseline : "pins"

    eval_run ||--o{ eval_result : "produces"
    eval_case ||--o{ eval_result : "judged in"
    eval_run ||--o{ eval_baseline : "referenced by"

    eval_suite {
        uuid id PK
        uuid org_id
        uuid site_id
        varchar suite_key
        varchar tool
        int version
        int case_count
        varchar status
    }

    eval_case {
        uuid id PK
        uuid suite_id FK
        varchar case_key
        jsonb input
        jsonb context
        jsonb expected_points
        jsonb forbidden_points
        text reference_output
        text_array tags
        varchar difficulty
        numeric weight
        varchar review_state
    }

    eval_run {
        uuid id PK
        uuid suite_id FK
        int suite_version
        varchar target_tool
        varchar target_prompt_version
        varchar target_model
        varchar trigger
        varchar git_sha
        varchar status
        numeric pass_rate
        numeric score_avg
        bigint token_usage
        timestamptz started_at
        timestamptz finished_at
    }

    eval_result {
        uuid id PK
        uuid run_id FK
        uuid case_id FK
        uuid suite_id FK
        text output_text
        jsonb output_json
        numeric score
        boolean passed
        jsonb point_hits
        jsonb violations
        int latency_ms
        jsonb judge_trace
        text error
    }

    eval_baseline {
        uuid id PK
        uuid suite_id FK
        uuid run_id FK
        uuid set_by
        timestamptz set_at
        text note
    }
```

源文件：`docs/er.mmd`。

---

## 5. 关键设计决策

1. **租户感知复合外键而不是应用层校验**：`eval_result` 同时用
   `(run_id, suite_id, org_id, site_id)` 和 `(case_id, suite_id, org_id, site_id)`
   两个复合外键，`eval_baseline` 用同样的租户字段；数据库层面保证结果/基线
   不会串套件、不会串租户或站点。为此 `eval_suite` 增加
   `UNIQUE (id, org_id, site_id)`，`eval_case` / `eval_run` 增加
   `UNIQUE (id, suite_id, org_id, site_id)`（PostgreSQL 要求被引用列组有唯一约束）。
   **注意**：这保证“不能链接到别的租户”，不保证“不能读到别的租户”；读取隔离
   仍需应用层查询过滤或 PostgreSQL RLS，本单未启用 RLS。
2. **结果唯一键**：`UNIQUE (run_id, case_id)` 是 AC-2 的唯一事实来源。worker 重试
   应捕获 `IntegrityError` 后改为更新原行，而不是插入第二行。
3. **`case_count` 是缓存列**：新增/删除用例时由应用层增减；数据库只保证 ≥ 0，
   不做触发器重算，避免批量导入时逐行锁表。
4. **分数口径写死为 0–100**：`pass_rate` 用百分比 `NUMERIC(5,2)`，
   `score_avg` / `score` 用 `NUMERIC(6,3)`，前端展示无需再猜 0–1 还是 0–100。
5. **基线保留历史**：`eval_baseline` 允许多条记录；清理脚本只要发现某 run
   被**任何**基线记录引用（即使该基线记录后来被软删除），就永久保留它的结果，
   避免“取消基线”后误删历史对照数据。
6. **软删除是业务语义**：所有表都有 `deleted_at`；硬删除只发生在
   (a) 迁移 downgrade、(b) 结果超过保留期后的清理。其余场景一律软删除。

---

## 6. 保留策略与清理脚本

策略：

- **普通运行结果保留 180 天**；
- **被设为基线的运行结果永久保留**；
- 只清理**终态**运行（`succeeded` / `failed` / `cancelled`）；`queued` / `running`
  即使 `started_at` 很旧也不动；
- 运行年龄按 `COALESCE(finished_at, started_at)` 计算，从未结束的运行按 `started_at`；
- 清理是**硬删除**，早先软删除的结果行在超过保留期后也会被物理回收；
- 判定为“超过 180 天”使用严格小于：恰好 180 天前的结果保留到下一轮。

**并发协议（基线永久保留）**：

- 协议要求事务隔离级别为 **`READ COMMITTED`**（PostgreSQL 默认）。
  `app.locks.acquire_baseline_lock()` 会先执行 `SHOW transaction_isolation`
  校验；在 `REPEATABLE READ` / `SERIALIZABLE` 下直接抛
  `LockProtocolError`，避免等锁后继续使用旧快照；
- 清理与基线写入共用 PostgreSQL 事务级 advisory lock
  `pg_advisory_xact_lock(830183000001)`（`app/locks.py`）；
- 清理在**选候选之前**取锁，并把筛选条件再次放进 `DELETE` 语句
  （`DELETE ... WHERE run_id IN (SELECT ... 仍满足策略)`），避免“选完 ID 后
  新增基线”的窗口；
- `app.retention._delete_candidates()` 是内部函数，自身也会取同一把锁；
  不要绕过 `cleanup_old_results()` / `set_baseline()` 直接调用；
- 基线写入必须走 `app.baseline.set_baseline()`：先取同一把锁，再校验 run 属于
  指定租户/套件、已是终态且仍有未删除的结果；没有结果的 run 拒绝设为基线；
- 锁在事务提交/回滚时自动释放。若清理先拿到锁，它会先删结果，基线写入随后
  看到 0 条结果而拒绝；若基线写入先拿到锁，清理随后会看到基线并跳过该 run。
  两端都绕过锁直接裸写数据库时，数据库无法单独阻止竞态。

用法：

```bash
export DATABASE_URL='postgresql+psycopg://USER:PASSWORD@127.0.0.1:5432/DB'

# 只看会删多少，不动数据
python scripts/cleanup_results.py --dry-run

# 正式清理，可指定窗口与批大小；--now 用于补跑/演练时冻结时间
python scripts/cleanup_results.py --days 180 --batch-size 500
python scripts/cleanup_results.py --now 2026-11-20T12:00:00Z
```

输出示例（实际数字随库变化）：

```json
{
  "now": "2026-11-20T12:00:00+00:00",
  "cutoff": "2026-05-24T12:00:00+00:00",
  "retention_days": 180,
  "deleted": 3,
  "dry_run": false
}
```

建议由夜间任务每天执行一次 `--dry-run` 并记录，再每周执行一次实际清理；
脚本是幂等的，重复执行不会重复删除。

清理只回收 `eval_result` 行；`eval_run` 元数据保留用于审计与趋势统计。
若后续要求连运行记录一起回收，需要另加工单并先确认审计要求。

---

## 7. 验收对照

| AC | 要求 | 实现 / 证据 |
|---|---|---|
| AC-1 | upgrade / downgrade 往返成功，`alembic check` 无漂移 | `tests/test_migration_roundtrip.py::test_upgrade_dowgrade_upgrade_and_zero_drift`；`scripts/migration-check.sh` 输出 `No new upgrade operations detected.`（`evidence/migration-check.txt`） |
| AC-2 | 同一 run 对同一用例重复写结果触发唯一约束 | `UNIQUE (run_id, case_id)` + 唯一索引；`tests/test_eval_result_unique.py::test_duplicate_result_for_same_run_and_case_is_rejected` 断言 `IntegrityError: uq_eval_result_run_case`；同文件 `test_database_index_supports_duplicate_detection` 校验索引存在 |
| AC-3 | 清理脚本删除 180 天前普通结果、保留基线运行结果（冻结时间测试） | `tests/test_cleanup_retention.py`：`NOW = 2026-11-20T12:00:00Z`，覆盖普通/基线/软删除基线/边界 180 天/运行中/无结束时间六类场景，并额外通过 `scripts/cleanup_results.py --now ...` 子进程验证 CLI |

本次实测结果：

- `96 passed`（真实 PostgreSQL 16.16；本次 1.81s）
- `alembic upgrade head` → `downgrade base` → `upgrade head` → `alembic check` 全部成功
- `alembic current`：`0002_tenant_aware_fks (head)`

---

## 8. 目录

```
app/
  db.py                 # Base、DATABASE_URL 读取
  enums.py              # 枚举与常量
  locks.py              # 基线与清理共用的 advisory lock
  baseline.py           # 基线写入（持锁 + 租户/套件校验）
  retention.py          # 180 天清理策略（可注入 now、DELETE 时复检）
  models/               # 5 张表的 SQLAlchemy 2 模型
  schemas/              # Pydantic 创建/读取 schema
migrations/
  env.py
  versions/0001_eval_framework_tables.py
  versions/0002_tenant_aware_fks.py
scripts/
  cleanup_results.py    # CLI：--dry-run / --days / --batch-size / --now
  migration-check.sh    # AC-1 证据
  test.sh               # 测试入口，支持 EVIDENCE_OUT
tests/                  # 83 项测试
docs/er.mmd             # Mermaid ER 图源文件
evidence/               # 测试与迁移证据
```

---

## 9. 假设与排除项

- 本单不实现 `case_count` 的自动维护逻辑；由套件编辑接口在增删用例时更新。
- 本单不实现“删除基线”接口；软删除 `eval_baseline` 即可，清理脚本仍保守保留其 run。
- `eval_run.suite_version` 是冗余字段（`suite_id` 已含版本信息），用于查询时免 join；
  写入方必须保证它与对应 `eval_suite.version` 一致，数据库不做跨表校验。
- 不提供 FastAPI 路由、认证、审计日志；这些属于后续工单。
- 测试库要求库名含 `test`，且 fixture 会 `DROP SCHEMA public CASCADE`；不要指向共享库。
