# 企业级接口自动化测试框架

本项目基于 `Pytest + Requests + Allure`，用于企业级接口自动化测试。

框架目标：

- 只维护一个 Excel 数据源：`data/excel/api_cases.xlsx`
- 每个 Sheet 自动映射为一个 YAML 文件和一个测试脚本
- 登录只在 Session 级执行一次
- 普通测试用例不关心 Token 的获取和传递
- 支持 401 自动刷新 Token
- 支持 Allure 报告与失败快照自动挂载

## 1. 环境准备

### 1.1 安装依赖

```bash
pip install -r requirements.txt
```

### 1.2 安装 Allure 命令行

请先安装 Allure Commandline，并确保 `allure` 已加入系统 `PATH`。

安装完成后，可以验证：

```bash
allure --version
```

## 2. 环境切换说明

框架支持多环境切换，配置加载顺序如下：

1. 先加载根目录下的 `.env`
2. 再加载 `.env.<ENV>`，后者会覆盖前者中的同名配置

示例：

- `ENV=dev` 时，加载 `.env` + `.env.dev`
- `ENV=prod` 时，加载 `.env` + `.env.prod`

### 2.1 推荐配置文件

建议按下面方式维护环境配置：

- `.env`：公共配置或本地默认配置
- `.env.dev`：测试环境配置
- `.env.prod`：生产环境配置

项目已提供以下示例文件：

- `.env.example`
- `.env.dev.example`
- `.env.prod.example`

可复制后自行修改：

```powershell
Copy-Item .env.dev.example .env.dev
Copy-Item .env.prod.example .env.prod
```

### 2.2 当前环境示例

测试环境示例：

```env
BASE_URL=http://test.lenszl.cn:30275
LOGIN_URL=http://test.lenszl.cn:30275/api/common/sys/login
```

生产环境示例：

```env
BASE_URL=https://jdz.lenszl.cn
LOGIN_URL=https://jdz.lenszl.cn/api/common/sys/login
```

说明：

- 如果生产环境登录路径不是 `/api/common/sys/login`，只需要修改 `LOGIN_URL`
- 当前脚本已经兼容 `BASE_URL` 带不带结尾 `/`

### 2.3 如何切换环境

方式一：使用 `Makefile`

```bash
make test ENV=dev
make test ENV=prod
```

方式二：使用 Python 任务脚本

```bash
python tools/task_runner.py test --env dev
python tools/task_runner.py test --env prod
```

方式三：直接设置环境变量后运行 Pytest

```powershell
$env:ENV = "prod"
pytest -q
```

## 3. 唯一 Excel 规则

当前框架只允许维护一个 Excel 数据源：

```text
data/excel/api_cases.xlsx
```

规则如下：

- 所有接口测试数据都维护在这一份 Excel 中
- 每个接口或测试模块使用一个独立 Sheet
- Sheet 名必须以 `test_` 开头
- Sheet 名必须与测试函数名完全一致
- 生成器会根据 Sheet 自动生成 YAML 和测试脚本

不要再拆分成多个 Excel 文件，否则会破坏当前自动映射规则。

## 4. 多 Sheet 映射规则

假设 `api_cases.xlsx` 中有下面这些 Sheet：

- `test_login`
- `test_message_list`
- `test_message_detail`

则自动映射关系如下：

- `test_login` -> `data/yaml/test_login.yaml` -> `testcases/test_login.py`
- `test_message_list` -> `data/yaml/test_message_list.yaml` -> `testcases/test_message_list.py`
- `test_message_detail` -> `data/yaml/test_message_detail.yaml` -> `testcases/test_message_detail.py`

说明：

- `data/yaml/*.yaml` 是运行时数据文件
- `testcases/test_*.py` 是自动生成的测试脚本
- 自动生成的文件可能被重新覆盖，因此不要手工修改

## 5. 自动生成命令

### 5.1 根据 Excel 生成 YAML 和测试脚本

```bash
python -m data.loader.test_generator --force
```

或者：

```bash
make generate ENV=dev
```

说明：

- `--force` 表示覆盖已有的自动生成脚本
- 修改了 `api_cases.xlsx` 后，建议重新执行一次生成命令

### 5.2 统一任务脚本

项目新增统一任务脚本：`tools/task_runner.py`

支持的命令如下：

- `generate`：生成 YAML 和测试脚本
- `test`：先生成，再运行 Pytest
- `allure`：先生成，再执行带 `allure-results` 的测试
- `report`：先生成，再运行测试，并生成静态 Allure 报告
- `open`：打开静态 Allure 报告
- `serve`：启动临时 Allure 报告服务
- `ci`：执行生成 + 测试 + 生成静态报告

示例：

```bash
python tools/task_runner.py report --env prod
```

## 6. 如何运行测试

推荐方式：

```bash
make test ENV=dev
```

如果本机没有 `make`，可以直接执行：

```bash
python tools/task_runner.py test --env dev
```

## 7. Allure 报告说明

### 7.1 最推荐的使用方式

```bash
make report ENV=dev
```

等价于：

```bash
python tools/task_runner.py report --env dev
```

这个命令会自动执行以下步骤：

1. 根据 Excel 重新生成 YAML 和测试脚本
2. 运行 Pytest 并输出 `allure-results`
3. 生成静态报告到 `allure-report`

### 7.2 报告目录

Allure 原始结果目录：

```text
allure-results
```

Allure 静态报告目录：

```text
allure-report
```

### 7.3 如何打开报告

打开静态报告：

```bash
make open-allure ENV=dev
```

或者：

```bash
python tools/task_runner.py open --env dev
```

启动临时报告服务：

```bash
make serve-allure ENV=dev
```

或者：

```bash
python tools/task_runner.py serve --env dev
```

说明：

- `allure-results` 是原始结果目录
- `allure-report` 是静态 HTML 报告目录
- 推荐优先使用静态报告，便于留档和分享

## 8. 断言模板化规则

你可以在 Excel 的 `asserts` 列中配置断言规则，内容格式为 JSON 数组。

示例：

```json
[
  {"type": "status_code", "expected": 200},
  {"type": "json_path_eq", "path": "code", "expected": 0},
  {"type": "exists", "path": "data"}
]
```

当前支持的断言类型：

- `status_code`
- `json_path_eq`
- `json_path_ne`
- `json_path_contains`
- `json_path_in`
- `exists`
- `not_exists`
- `length_eq`
- `body_contains`

### 8.1 默认断言生成规则

如果 `asserts` 为空，框架会根据下面两个字段自动补全默认断言：

- `expected_status`
- `expected_code`

例如：

- `expected_status=200`
- `expected_code=0`

则会自动生成类似下面的断言：

```json
[
  {"type": "status_code", "expected": 200},
  {"type": "json_path_eq", "path": "code", "expected": 0}
]
```

## 9. Excel 字段建议

推荐每个 Sheet 使用下面这些列：

| 列名 | 说明 |
| --- | --- |
| `id` | 用例编号 |
| `name` | 用例名称 |
| `method` | 请求方法，如 `GET`、`POST` |
| `url` | 接口路径，推荐使用相对路径 |
| `headers` | 请求头，JSON 字符串 |
| `params` | Query 参数，JSON 字符串 |
| `json` | JSON 请求体，JSON 字符串 |
| `data` | 表单或纯文本请求体 |
| `expected_status` | 期望 HTTP 状态码 |
| `expected_code` | 期望业务码 |
| `asserts` | 断言规则，JSON 数组 |
| `use_settings_login` | 登录测试是否直接使用配置文件中的账号密码 |

## 10. 新接口添加示例

假设你要新增下面这个接口：

```text
GET /api/message/index/2267
```

### 第 1 步：在 Excel 中新增 Sheet

打开：

```text
data/excel/api_cases.xlsx
```

新增一个 Sheet，命名为：

```text
test_message_detail
```

### 第 2 步：在 Sheet 中新增一条数据

你可以填写如下内容：

| 列名 | 示例值 |
| --- | --- |
| `id` | `detail_001` |
| `name` | `消息详情查询` |
| `method` | `GET` |
| `url` | `/api/message/index/2267` |
| `expected_status` | `200` |
| `expected_code` | `0` |
| `asserts` | `[{"type":"status_code","expected":200},{"type":"json_path_eq","path":"code","expected":0},{"type":"exists","path":"data.list"}]` |

注意：

- 不要在 Excel 中维护 Token
- 框架会自动登录并把 Token 注入请求头
- 如果接口只需要通用请求逻辑，不需要手写测试脚本

### 第 3 步：生成 YAML 和测试脚本

```bash
make generate ENV=dev
```

或者：

```bash
python -m data.loader.test_generator --force
```

### 第 4 步：执行测试

```bash
make test ENV=dev
```

## 11. 日常推荐工作流

推荐按下面顺序操作：

1. 编辑 `data/excel/api_cases.xlsx`
2. 执行 `make generate ENV=dev`
3. 执行 `make test ENV=dev`
4. 需要报告时执行 `make report ENV=dev`

如果你要切换生产环境，只需要把命令中的 `ENV=dev` 改成 `ENV=prod`。
