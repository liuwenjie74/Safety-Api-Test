# 企业级接口自动化测试框架（Pytest + Requests + Allure）

## 1. 项目简介
本项目为企业级接口自动化测试框架，强调：
- **Excel 为唯一数据源**，运行时转换为 YAML；
- **登录态会话保持**，Session 级登录一次；
- **测试用例不感知 Token**，由 RequestClient 自动注入；
- **Pytest + Requests + Allure 标准化集成**。

支持多环境切换与多 Sheet → 多模块自动映射，可直接用于企业接口测试体系。
新增能力：
- **401 自动刷新 Token**（防止登录态失效导致批量失败）
- **Excel 模板生成器**（一键生成标准用例模板）
- **CI/CD Pipeline**（GitHub Actions 可直接运行）

## 2. 目录结构与职责
```
E:\Python\Safety-Api-Test
├─ config/                 # 配置中心（环境、账号、路径）
│  ├─ settings.py           # .env 加载 + 运行时配置
├─ data/
│  ├─ excel/                # Excel 用例（唯一数据源）
│  ├─ yaml/                 # 自动生成 YAML（运行时数据）
│  └─ loader/
│     ├─ excel_to_yaml.py   # Excel → YAML 转换器
│     └─ hot_loader.py      # 热加载器（Excel 更新自动同步）
├─ common/
│  ├─ context.py            # 会话上下文（Token/请求快照）
│  ├─ auth.py               # 登录封装与 Token 提取
│  └─ logger.py             # 日志与脱敏过滤
├─ base/
│  └─ request_client.py     # Requests 二次封装（自动注入 Token）
├─ testcases/               # 测试用例（仅编排与断言）
├─ conftest.py              # Pytest 全局配置与 Session 登录
└─ pytest.ini               # Pytest 配置
```

## 3. 多环境切换
支持 `.env` + `.env.<ENV>` 机制：

1. 默认加载 `.env`
2. 设置 `ENV=dev/test/prod` 后加载 `.env.<ENV>` 覆盖

示例：
```
ENV=test
```
则加载顺序为：
- `.env`
- `.env.test`

常用配置（可放在 `.env` 或 `.env.test`）：
```
BASE_URL=http://test.lenszl.cn:30275
LOGIN_URL=http://test.lenszl.cn:30275/api/common/sys/login
LOGIN_METHOD=POST
LOGIN_HEADERS={"Content-Type":"application/json"}
LOGIN_PAYLOAD={"userAccount":"xxx","password":"yyy"}
TOKEN_PATH=data
TOKEN_HEADER=token
REQUEST_TIMEOUT=15
MULTI_SHEET_MODE=sheet
```

## 4. 401 自动刷新 Token
当接口返回 `401` 时：
1. RequestClient 会触发刷新锁；
2. 重新执行登录获取新 Token；
3. 自动重试原请求（默认最多 1 次）。

你可以在 `conftest.py` 中调整 `max_retry_401`：
```
RequestClient(context=session_context, auth_service=auth_service, max_retry_401=1)
```

## 5. Excel 用例维护规范
Excel 是唯一数据源，建议列结构如下：

| 列名 | 描述 |
|---|---|
| id | 用例编号 |
| name | 用例名称 |
| method | 请求方法（GET/POST/PUT） |
| url | 接口路径（推荐相对路径） |
| headers | JSON 字符串，可为空 |
| params | Query 参数 JSON 字符串 |
| json | JSON Body 字符串 |
| data | Form Body / Text |
| expected_status | 期望 HTTP 状态码 |
| expected_code | 期望业务 code |

### JSON 列写法示例
```
{"dataType":3,"startTime":"2026-03-01 00:00:00","endTime":"2026-03-30 23:59:59"}
```

空值直接留空即可，框架会自动清洗。

### 断言模板化（asserts）
你可以在 Excel 的 `asserts` 列中写入 **JSON 数组**，用于模板化断言。

支持的断言类型：
- `status_code`
- `json_path_eq`
- `json_path_ne`
- `json_path_contains`
- `json_path_in`
- `exists`
- `not_exists`
- `length_eq`
- `body_contains`

示例：
```
[
  {"type":"status_code","expected":200},
  {"type":"json_path_eq","path":"code","expected":200},
  {"type":"length_eq","path":"data","expected":10}
]
```

如果 `asserts` 为空，则默认使用：
- `expected_status`（断言 status_code）
- `expected_code`（断言 JSON 路径 `code`）

## 6. 多 Sheet → 多模块自动映射
Excel 多 Sheet 时，默认将 **Sheet 名称映射为 YAML 文件名**（推荐）。

### 模式配置
`MULTI_SHEET_MODE` 可选：
- `sheet`：YAML 文件名 = Sheet 名称
- `excel_sheet`：YAML 文件名 = Excel名__Sheet名

### 测试函数映射规则
当 `testcases/test_xxx.py` 中存在 `test_abc`：
1. 若 `data/excel/test_abc.xlsx` 存在，则直接使用；
2. 否则在所有 Excel 中搜索 Sheet = `test_abc`，命中则生成 `data/yaml/test_abc.yaml`。

## 7. Excel 模板生成器
模板生成脚本：
```
python -m data.loader.template_generator --path data/excel/template.xlsx --sheet cases
```
生成后请在 Excel 中按模板规范维护用例数据。

## 8. 运行方式
### 安装依赖
```
pip install pytest requests pyyaml pandas openpyxl allure-pytest
```

### 运行测试
```
pytest -q
```

### 生成 Allure 报告
```
pytest -q --alluredir=allure-results
allure serve allure-results
```

## 9. 登录态与 Token 机制
1. 登录接口封装在 `common/auth.py`，只在 Session 级执行一次；
2. Token 从 `response.data` 提取（由 `TOKEN_PATH` 配置）；
3. Token 保存于 `SessionContext`；
4. 所有请求由 `RequestClient` 自动注入 Token Header（默认 `token`）。

### 重要限制
- 测试用例中禁止直接调用登录接口；
- YAML 中禁止保存 Token；
- Token 明文不会输出到日志（自动脱敏）。

## 10. Excel → YAML 热加载流程
1. Pytest 收集阶段触发 `pytest_generate_tests`；
2. 自动比较 Excel/YAML 时间戳；
3. Excel 发生修改 → 自动重新生成 YAML；
4. YAML 驱动参数化执行。

## 11. 示例用例
示例用例文件：
- Excel：`data/excel/test_message_list.xlsx`
- YAML：`data/yaml/test_message_list.yaml`
- 用例：`testcases/test_message_list.py`

用例只关心断言，不关心登录。

## 12. CI/CD Pipeline（GitHub Actions）
已提供完整配置文件：
```
.github/workflows/ci.yml
```
在 GitHub 仓库中配置以下 Secrets（否则会因为登录失败而报错）：
- `BASE_URL`
- `LOGIN_URL`
- `LOGIN_METHOD`
- `LOGIN_HEADERS`
- `LOGIN_PAYLOAD`
- `TOKEN_PATH`
- `TOKEN_HEADER`
- `TOKEN_PREFIX`

CI 将执行：
```
pytest -q --alluredir=allure-results
```
并上传 `allure-results` 作为构建产物。
