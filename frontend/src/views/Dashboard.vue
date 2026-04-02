<template>
  <div>
    <a-row :gutter="16" style="margin-bottom: 24px">
      <a-col :span="6">
        <a-card><a-statistic title="需求总数" :value="stats.total_requirements" /></a-card>
      </a-col>
      <a-col :span="6">
        <a-card><a-statistic title="测试用例总数" :value="stats.total_testcases" /></a-card>
      </a-col>
      <a-col :span="6">
        <a-card><a-statistic title="生成任务" :value="stats.total_generation_jobs" /></a-card>
      </a-col>
      <a-col :span="6">
        <a-card>
          <a-statistic title="执行通过率" :value="stats.execution_pass_rate ?? '-'" suffix="%" :precision="1" />
        </a-card>
      </a-col>
    </a-row>

    <a-row :gutter="16" style="margin-bottom: 24px">
      <a-col :span="8">
        <a-card title="用例类型分布">
          <div v-for="(val, key) in stats.testcases_by_type" :key="key" style="margin-bottom: 8px">
            <span>{{ typeLabels[key] || key }}: </span>
            <a-tag :color="typeColors[key]">{{ val }}</a-tag>
          </div>
        </a-card>
      </a-col>
      <a-col :span="8">
        <a-card title="用例优先级分布">
          <div v-for="(val, key) in stats.testcases_by_priority" :key="key" style="margin-bottom: 8px">
            <span>{{ key }}: </span>
            <a-tag :color="priorityColors[key]">{{ val }}</a-tag>
          </div>
        </a-card>
      </a-col>
      <a-col :span="8">
        <a-card title="生成任务状态">
          <div v-for="(val, key) in stats.generation_jobs_by_status" :key="key" style="margin-bottom: 8px">
            <span>{{ statusLabels[key] || key }}: </span>
            <a-tag :color="statusColors[key]">{{ val }}</a-tag>
          </div>
        </a-card>
      </a-col>
    </a-row>

    <a-row :gutter="16">
      <a-col :span="12">
        <a-card title="最近生成任务">
          <a-table :dataSource="stats.recent_generation_jobs" :columns="genColumns" :pagination="false" size="small" rowKey="id" />
        </a-card>
      </a-col>
      <a-col :span="12">
        <a-card title="最近执行任务">
          <a-table :dataSource="stats.recent_execution_jobs" :columns="execColumns" :pagination="false" size="small" rowKey="id" />
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '../api'

const stats = ref<any>({
  total_requirements: 0, total_testcases: 0, total_generation_jobs: 0,
  total_execution_jobs: 0, execution_pass_rate: null,
  testcases_by_type: {}, testcases_by_priority: {},
  generation_jobs_by_status: {},
  recent_generation_jobs: [], recent_execution_jobs: [],
})

const typeLabels: Record<string, string> = { functional: '功能测试', ui: 'UI测试', api: '接口测试' }
const typeColors: Record<string, string> = { functional: 'blue', ui: 'purple', api: 'green' }
const priorityColors: Record<string, string> = { P0: 'red', P1: 'orange', P2: 'blue', P3: 'default' }
const statusLabels: Record<string, string> = { pending: '等待中', running: '运行中', success: '成功', failed: '失败' }
const statusColors: Record<string, string> = { pending: 'default', running: 'processing', success: 'success', failed: 'error' }

const genColumns = [
  { title: '任务名', dataIndex: 'name', ellipsis: true },
  { title: '类型', dataIndex: 'job_type', customRender: ({ text }: any) => typeLabels[text] || text },
  { title: '状态', dataIndex: 'status', customRender: ({ text }: any) => statusLabels[text] || text },
  { title: '进度', dataIndex: 'progress', customRender: ({ text }: any) => `${text}%` },
]
const execColumns = [
  { title: '任务名', dataIndex: 'name', ellipsis: true },
  { title: '状态', dataIndex: 'status', customRender: ({ text }: any) => statusLabels[text] || text },
  { title: '通过', dataIndex: 'passed' },
  { title: '失败', dataIndex: 'failed' },
]

onMounted(async () => {
  const res: any = await api.get('/dashboard/stats')
  stats.value = res.data
})
</script>
