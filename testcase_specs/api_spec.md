# 接口测试用例规范

## 用例编写标准

### 用例结构
每条接口测试用例必须包含以下要素：

| 要素 | 必填 | 说明 |
|------|------|------|
| 用例编号 | 是 | 格式: API-{模块缩写}-{序号}，如 API-LOGIN-001 |
| 标题 | 是 | {接口名称} - {测试场景} |
| 模块 | 是 | 接口所属业务模块 |
| 优先级 | 是 | P0/P1/P2/P3 |
| 接口路径 | 是 | HTTP_METHOD /path |
| 接口基本信息 | 是 | URL、认证方式、Content-Type |
| 请求信息 | 是 | Headers + 请求体 JSON |
| 断言规则 | 是 | 表格形式：断言类型、路径、期望值、匹配方式 |
| 测试场景矩阵 | 是 | 包含正常、异常、边界场景 |
| 变量依赖 | 否 | {{BASE_URL}}、{{TOKEN}} 等变量声明 |

### 场景覆盖要求
每个接口至少覆盖以下场景：
1. **正常场景**：有效参数，预期成功响应
2. **参数缺失**：必填参数不传
3. **参数格式错误**：类型不匹配、格式非法
4. **边界值**：空字符串、超长字符串、极大/极小数值
5. **鉴权校验**：未携带Token、过期Token（需鉴权接口）
6. **幂等性**：重复请求的处理（POST/PUT接口）

### 断言类型说明
| 类型 | 说明 | 示例 |
|------|------|------|
| status_code | HTTP 状态码 | 200, 400, 401, 500 |
| json_field | JSONPath 字段值 | $.code equals 0 |
| not_null | 字段非空 | $.data.token not_null |
| response_time | 响应时间(ms) | less_than 2000 |
| regex | 正则匹配 | $.data.id regex /^\d+$/ |
| contains | 包含子串 | $.message contains "成功" |

### 输出模板

```markdown
## 测试用例：{用例编号}

**标题**: {接口名称} - {测试场景}
**模块**: {接口所属模块}
**优先级**: {P0 | P1 | P2 | P3}
**接口路径**: {HTTP_METHOD} {path}

### 接口基本信息
- **完整 URL**: `{{BASE_URL}}{path}`
- **认证方式**: {Bearer Token | Cookie | 无}
- **Content-Type**: {application/json | multipart/form-data}

### 请求信息
**Headers**:
| Key | Value | 必须 |
|-----|-------|------|
| Authorization | Bearer {{TOKEN}} | 是 |
| Content-Type | application/json | 是 |

**请求体**:
```json
{
  "field1": "value1",
  "field2": "value2"
}
```

### 断言规则
| 断言类型 | 断言路径 | 期望值 | 匹配方式 |
|----------|----------|--------|----------|
| status_code | - | 200 | equals |
| json_field | $.code | 0 | equals |
| json_field | $.data.token | - | not_null |
| response_time | - | 2000 | less_than |

### 测试场景矩阵
| 场景 | 关键输入变化 | 预期 status_code | 预期 code | 备注 |
|------|-------------|-----------------|-----------|------|
| 正常请求 | 全部有效参数 | 200 | 0 | 主流程 |
| 参数缺失 | 缺少必填字段 | 400 | - | 参数校验 |
| 格式错误 | 字段格式非法 | 400 | - | 格式校验 |
| 未鉴权 | 不携带Token | 401 | - | 鉴权校验 |

### 变量依赖
- `{{BASE_URL}}`: 从执行环境配置读取
- `{{TOKEN}}`: 从前置登录用例响应中提取

### 备注
{YApi接口链接或特殊说明}
```
