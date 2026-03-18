# 企业级接口自动化测试框架

本项目基于 `Pytest + Requests + Allure`，用于企业级接口自动化测试。框架核心目标是：

- Excel 作为唯一数据源
- YAML 作为运行时数据格式
- 登录态自动管理，测试用例不关心 Token
- 支持按 Sheet 自动生成 YAML 和测试脚本

## 1. 如何运行

### 1.1 安装依赖

```bash
pip install -r requirements.txt
```

### 1.2 运行测试

```bash
pytest -q
```

### 1.3 生成 Allure 报告

最推荐的使用方式：

```bash
pytest -q --alluredir=allure-results --clean-alluredir
allure generate allure-results -o allure-report --clean
allure open allure-report
```

这组命令的含义是：

- 第 1 条：执行测试并重新生成干净的 Allure 原始结果
- 第 2 条：把原始结果生成为静态 HTML 报告
- 第 3 条：打开静态报告

如果只是临时查看一次报告，也可以使用：

```bash
pytest -q --alluredir=allure-results
allure serve allure-results
```

注意：

- `allure serve allure-results` 会启动一个临时服务并自动打开报告
- 这种方式适合临时查看，但不会把最终报告固定输出到 `allure-report`
- 如果需要留档、发给别人或反复打开，优先使用上面的“最推荐的使用方式”

Allure 原始结果目录：

```text
E:\Python\Safety-Api-Test\allure-results
```

如果需要单独生成静态 HTML 报告：

```bash
allure generate allure-results -o allure-report --clean
```

静态报告目录：

```text
E:\Python\Safety-Api-Test\allure-report
```

静态报告推荐打开方式：

```bash
allure open allure-report
```

## 2. 唯一 Excel 规则

当前框架只允许一个 Excel 数据文件：

```text
data/excel/api_cases.xlsx
```

所有接口测试数据都必须维护在这个文件中，不再拆分成多个 Excel。

每个接口或测试模块使用一个独立 Sheet。

## 3. 多 Sheet 映射规则

映射规则如下：

- Sheet 名必须以 `test_` 开头
- Sheet 名等于测试函数名
- Sheet 名同时也是 YAML 文件名

例如 `api_cases.xlsx` 中有以下 Sheet：

- `test_login`
- `test_message_list`
- `test_message_detail`

对应关系为：

- `test_login` -> `testcases/test_login.py` -> `data/yaml/test_login.yaml`
- `test_message_list` -> `testcases/test_message_list.py` -> `data/yaml/test_message_list.yaml`
- `test_message_detail` -> `testcases/test_message_detail.py` -> `data/yaml/test_message_detail.yaml`

## 4. 自动生成命令

根据 `api_cases.xlsx` 中的 Sheet 自动生成测试脚本和 YAML：

```bash
python -m data.loader.test_generator
```

如果需要覆盖已存在的测试脚本：

```bash
python -m data.loader.test_generator --force
```

生成器会自动处理两类文件：

- `testcases/test_xxx.py`
- `data/yaml/test_xxx.yaml`

## 5. 断言模板化规则

在 Excel 中可以使用 `asserts` 列定义断言模板，内容为 JSON 数组。

示例：

```json
[
  {"type": "status_code", "expected": 200},
  {"type": "json_path_eq", "path": "code", "expected": 200}
]
```

目前支持的断言类型：

- `status_code`
- `json_path_eq`
- `json_path_ne`
- `json_path_contains`
- `json_path_in`
- `exists`
- `not_exists`
- `length_eq`
- `body_contains`

如果 `asserts` 为空，框架会自动根据以下字段补全默认断言：

- `expected_status`
- `expected_code`

也就是说，只填这两个字段，也可以直接运行。

## 6. Excel 字段建议

推荐在 Sheet 中使用这些列：

| 列名 | 说明 |
| --- | --- |
| `id` | 用例编号 |
| `name` | 用例名称 |
| `method` | 请求方法，如 `GET`、`POST` |
| `url` | 接口路径，推荐写相对路径 |
| `headers` | 请求头，JSON 字符串 |
| `params` | 查询参数，JSON 字符串 |
| `json` | JSON 请求体，JSON 字符串 |
| `data` | 表单或纯文本请求体 |
| `expected_status` | 期望 HTTP 状态码 |
| `expected_code` | 期望业务码 |
| `asserts` | 断言模板，JSON 数组 |
| `use_settings_login` | 登录接口测试时，是否直接使用配置文件中的账号密码 |

## 7. 新接口添加示例

假设新增接口：

```text
GET /api/message/index/2267
```

返回体中关注：

- HTTP 状态码为 `200`
- 业务字段 `code` 为 `200`

添加步骤如下。

### 第 1 步：在 Excel 中新增 Sheet

打开：

```text
data/excel/api_cases.xlsx
```

新增一个 Sheet，名称为：

```text
test_message_detail
```

### 第 2 步：填写一条测试数据

示例数据如下：

| 列名 | 示例值 |
| --- | --- |
| `id` | `detail_001` |
| `name` | `消息详情查询` |
| `method` | `GET` |
| `url` | `/api/message/index/2267` |
| `expected_status` | `200` |
| `expected_code` | `200` |
| `asserts` | `[{"type":"status_code","expected":200},{"type":"json_path_eq","path":"code","expected":200}]` |

注意：

- 不需要填写 Token
- Token 会由框架自动登录并注入请求头

### 第 3 步：自动生成 YAML 和测试脚本

```bash
python -m data.loader.test_generator --force
```

### 第 4 步：执行测试

```bash
pytest -q
```

## 8. 当前工作方式总结

日常使用时，只需要记住这几个动作：

1. 在 `data/excel/api_cases.xlsx` 中维护或新增 Sheet
2. 运行 `python -m data.loader.test_generator --force`
3. 运行 `pytest -q`
4. 需要报告时运行 Allure 命令
