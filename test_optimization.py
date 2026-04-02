#!/usr/bin/env python3
"""测试优化后的功能测试用例生成效果"""

import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, '/Users/jinrishuiyinxiangji/PycharmProjects/qa_testcase')

from jinja2 import Template
from backend.config import settings
from backend.app.core.ai.chat_client import ChatClient

# 从任务28获取的需求内容
REQUIREMENT_CONTENT = """# 用户日常唤活送会员策略（安卓单端）

## 一、需求背景

为了提升安卓用户活跃度，对符合条件的用户进行唤活激励，赠送8天个人会员权益。

## 二、目标人群

### 1. 人群规则

符合以下**所有**条件的用户才会被圈选：

- 属于高价值用户 **OR** 整5天未启动用户（即上次启动时间为当前日期-6天）
- **非**稳定低频用户
- 注册时间≥60天
- 从未开通个人会员
- 当前不是个人会员

### 2. 人群定义

#### 高价值用户定义：
- 近30天付费金额≥5元 **OR** 
- 近30天启动天数≥15天 **AND** 平均每天启动次数≥3次 **AND** 上次活跃时间≤7天

#### 稳定低频用户定义：
- 近30天启动天数≥15天 **AND** 平均每天启动次数≤2次

#### 整5天未启动用户定义：
- 上次启动时间 = 当前日期 - 6天

## 三、功能逻辑

### 1. 启动APP唤活

- 用户命中AB实验实验组，且满足上述人群规则
- APP冷启动时，弹出唤活会员领取弹框
- 弹框文案：「您有8天免费会员待领取」
- 用户点击「立即领取」后，发放8天个人会员权益
- 同一用户仅可领取一次

### 2. 短信触达

- 针对符合人群规则但近期未启动APP的用户
- 发送短信内容：「【今日水印相机】您有8天免费会员待领取。启动APP即可领取，限时开放。拒收请回复R」
- 同一用户仅发送1次
- 用户回复R后停止对该用户发送

## 四、配置控制

- 总开关控制功能是否开启
- AB实验控制用户流量分配
- 短信开关控制是否发送短信

## 五、数据指标

需要统计的核心指标：
- 唤活弹框曝光UV
- 唤活弹框点击UV
- 会员领取UV
- 短信发送成功率
- 短信拒收率

## 六、技术实现

### 人群圈选SQL逻辑

WITH biz AS (
  SELECT 
    user_id,
    -- 高价值用户判断
    CASE WHEN pay_amount_30d >= 5 OR (active_days_30d >= 15 AND avg_daily_starts >= 3 AND last_active_days <= 7) THEN 1 ELSE 0 END AS is_high_value,
    -- 稳定低频用户判断
    CASE WHEN active_days_30d >= 15 AND avg_daily_starts <= 2 THEN 1 ELSE 0 END AS is_stable_low_freq,
    -- 整5天未启动判断
    CASE WHEN last_launch_date = DATE_SUB(CURDATE(), INTERVAL 6 DAY) THEN 1 ELSE 0 END AS is_5days_no_launch,
    register_days,
    has_personal_member_history,
    current_is_member,
    last_launch_date
  FROM user_behavior_stats
  WHERE platform = 'android'
)
SELECT 
  user_id,
  last_launch_date,
  register_days,
  has_personal_member_history,
  current_is_member
FROM biz 
WHERE (is_high_value = 1 OR is_5days_no_launch = 1)
  AND is_stable_low_freq = 0
  AND register_days >= 60
  AND has_personal_member_history = 0
  AND current_is_member = 0
ORDER BY last_launch_date DESC
LIMIT 10000;

-- 计算平均每日启动次数
avg_active_days_per_active_week
"""

SPEC_CONTENT = """# 功能测试用例编写规范

## 用例结构

每条测试用例必须包含以下字段：

### 用例编号
格式：TC-ACT-XXX（ACT表示活动类）
示例：TC-ACT-001

### 用例标题
简洁描述测试场景

### 优先级
- P0：核心流程、阻断业务、关键状态流转
- P1：重要功能、核心异常、关键业务规则
- P2：常规功能、边界值、常见异常
- P3：低频场景、UI、提示信息

### 所属模块
填写具体业务模块，如：用户唤活策略 > 启动激励

### 前置条件
列出执行测试前必须满足的条件，每条一行

### 测试步骤
使用表格形式，包含：步骤、操作、预期结果三列

### 预期结果
描述执行完所有步骤后期望看到的结果
"""

async def test_generation():
    """测试用例生成"""
    
    # 1. 渲染Prompt
    print("🔧 渲染Prompt...")
    prompt_path = settings.prompts_dir / "functional_testcase.j2"
    template = Template(prompt_path.read_text(encoding="utf-8"))
    prompt = template.render(
        spec_content=SPEC_CONTENT,
        requirement_content=REQUIREMENT_CONTENT,
        target_module="",
        expected_count="",
    )
    
    print(f"📝 Prompt长度: {len(prompt)} 字符")
    print("=" * 50)
    
    # 2. 调用AI生成
    print("🤖 调用AI生成测试用例...")
    client = ChatClient()
    
    try:
        result = await client.generate(
            prompt=prompt,
            system_prompt="你是一位资深QA工程师，精通测试用例设计。",
            model_alias="chat-pro",
            max_tokens=8192,
            temperature=0.7
        )
        
        print("\n✅ 生成完成！")
        print("=" * 50)
        print(result)
        
        # 简单统计
        test_case_count = result.count("## TC-")
        print(f"\n📊 检测到测试用例数量: {test_case_count}")
        
        # 检查是否包含测试点清单
        if "TO-" in result:
            to_count = result.count("TO-")
            print(f"📊 检测到测试点数量: {to_count}")
            if "测试点清单" in result or "Step1" in result:
                print("✅ 包含测试点清单输出")
            else:
                print("⚠️  包含TO-编号但未明确输出测试点清单")
        else:
            print("❌ 未检测到测试点编号(TO-XXX)")
            
    except Exception as e:
        print(f"❌ 生成失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_generation())