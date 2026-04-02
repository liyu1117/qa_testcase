<template>
  <div>
    <div style="margin-bottom: 16px; display: flex; justify-content: space-between">
      <a-select v-model:value="statusFilter" placeholder="状态" style="width: 120px" allowClear @change="loadData">
        <a-select-option value="pending">等待中</a-select-option>
        <a-select-option value="running">运行中</a-select-option>
        <a-select-option value="success">成功</a-select-option>
        <a-select-option value="failed">失败</a-select-option>
      </a-select>
      <a-button type="primary" @click="openCreate">新建执行任务</a-button>
    </div>

    <a-table :dataSource="list" :columns="columns" :loading="loading" :pagination="pagination" @change="onTableChange" rowKey="id" size="middle">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <a-tag :color="statusColors[record.status]">{{ statusLabels[record.status] }}</a-tag>
        </template>
        <template v-if="column.key === 'exec_mode'">
          <a-tag :color="record.execution_mode === 'pytest' ? 'blue' : 'cyan'">{{ record.execution_mode === 'pytest' ? 'pytest' : 'httpx' }}</a-tag>
        </template>
        <template v-if="column.key === 'result'">
          <a-space>
            <a-tag color="green">通过 {{ record.passed }}</a-tag>
            <a-tag color="red">失败 {{ record.failed }}</a-tag>
            <a-tag v-if="record.skipped > 0">跳过 {{ record.skipped }}</a-tag>
          </a-space>
        </template>
        <template v-if="column.key === 'duration'">
          {{ record.duration ? `${record.duration.toFixed(1)}s` : '-' }}
        </template>
        <template v-if="column.key === 'actions'">
          <a-space>
            <a @click="openResults(record)">查看结果</a>
            <a v-if="record.report_path" @click="handleDownloadReport(record.id)">下载报告</a>
          </a-space>
        </template>
      </template>
    </a-table>

    <!-- 执行结果抽屉 -->
    <a-drawer v-model:open="showResults" title="执行结果" width="900">
      <template v-if="currentJob">
        <a-descriptions :column="2" bordered size="small" style="margin-bottom: 16px">
          <a-descriptions-item label="任务名称">{{ currentJob.name }}</a-descriptions-item>
          <a-descriptions-item label="状态">
            <a-tag :color="statusColors[currentJob.status]">{{ statusLabels[currentJob.status] }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="执行模式">
            <a-tag :color="currentJob.execution_mode === 'pytest' ? 'blue' : 'cyan'">{{ currentJob.execution_mode === 'pytest' ? 'pytest 脚本' : '内置引擎' }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="总用例">{{ currentJob.total_cases }}</a-descriptions-item>
          <a-descriptions-item label="耗时">{{ currentJob.duration ? `${currentJob.duration.toFixed(1)}s` : '-' }}</a-descriptions-item>
          <a-descriptions-item label="通过/失败">
            <span style="color: green">{{ currentJob.passed }}</span> / <span style="color: red">{{ currentJob.failed }}</span>
          </a-descriptions-item>
          <a-descriptions-item v-if="currentJob.pytest_script_path" label="脚本路径" :span="2">
            <code style="word-break: break-all; font-size: 12px">{{ currentJob.pytest_script_path }}</code>
          </a-descriptions-item>
          <a-descriptions-item v-if="currentJob.error_message" label="错误信息" :span="2">
            <span style="color: red">{{ currentJob.error_message }}</span>
          </a-descriptions-item>
        </a-descriptions>

        <a-tabs v-model:activeKey="resultTab" style="margin-top: 16px">
          <!-- Tab 1: 执行结果 -->
          <a-tab-pane key="results" tab="执行结果">
            <a-table :dataSource="results" :columns="resultColumns" :loading="resultsLoading" :pagination="resultsPag" @change="onResultsChange" rowKey="id" size="small">
              <template #bodyCell="{ column, record: r }">
                <template v-if="column.key === 'result_status'">
                  <a-tag :color="r.status === 'pass' ? 'green' : r.status === 'fail' ? 'red' : r.status === 'error' ? 'volcano' : 'default'">{{ resultStatusLabels[r.status] || r.status }}</a-tag>
                </template>
                <template v-if="column.key === 'result_actions'">
                  <a @click="openResultDetail(r)">详情</a>
                </template>
              </template>
            </a-table>
          </a-tab-pane>

          <!-- Tab 2: pytest 脚本 -->
          <a-tab-pane key="script" tab="pytest 脚本">
            <div v-if="pytestScript" style="position: relative">
              <div style="margin-bottom: 12px">
                <a-button type="primary" size="small" @click="downloadScript">下载脚本</a-button>
                <a-button size="small" style="margin-left: 8px" @click="copyScript">复制代码</a-button>
              </div>
              <pre class="code-block">{{ pytestScript }}</pre>
            </div>
            <a-empty v-else description="未找到 pytest 脚本（需先通过接口测试用例生成任务生成）" />
          </a-tab-pane>
        </a-tabs>
      </template>
    </a-drawer>

    <!-- 单条结果详情 -->
    <a-modal v-model:open="showResultDetail" title="执行详情" :footer="null" width="700px">
      <template v-if="resultDetail">
        <a-descriptions :column="2" bordered size="small">
          <a-descriptions-item label="用例ID">{{ resultDetail.testcase_id }}</a-descriptions-item>
          <a-descriptions-item label="用例名称">{{ resultDetail.testcase_title || '-' }}</a-descriptions-item>
          <a-descriptions-item label="状态">
            <a-tag :color="resultDetail.status === 'pass' ? 'green' : resultDetail.status === 'fail' ? 'red' : resultDetail.status === 'error' ? 'volcano' : 'default'">{{ resultStatusLabels[resultDetail.status] || resultDetail.status }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="重试次数">{{ resultDetail.retry_count }}</a-descriptions-item>
          <a-descriptions-item label="执行时间" :span="2">{{ resultDetail.executed_at || '-' }}</a-descriptions-item>
          <a-descriptions-item v-if="resultDetail.pytest_nodeid" label="测试节点" :span="2">
            <code>{{ resultDetail.pytest_nodeid }}</code>
          </a-descriptions-item>
          <a-descriptions-item v-if="currentJob?.pytest_script_path" label="脚本存储路径" :span="2">
            <code style="word-break: break-all; font-size: 12px">{{ currentJob.pytest_script_path }}</code>
          </a-descriptions-item>
        </a-descriptions>
        <template v-if="resultDetail.request_info">
          <h4 style="margin-top: 16px">请求信息</h4>
          <pre style="background: #f5f5f5; padding: 12px; border-radius: 4px; overflow: auto; max-height: 200px">{{ JSON.stringify(resultDetail.request_info, null, 2) }}</pre>
        </template>
        <template v-if="resultDetail.response_info">
          <h4 style="margin-top: 12px">响应信息</h4>
          <pre style="background: #f5f5f5; padding: 12px; border-radius: 4px; overflow: auto; max-height: 200px">{{ JSON.stringify(resultDetail.response_info, null, 2) }}</pre>
        </template>
        <template v-if="resultDetail.assertion_results?.length">
          <h4 style="margin-top: 12px">断言结果</h4>
          <a-table :dataSource="resultDetail.assertion_results" :columns="assertionResultColumns" :pagination="false" size="small" />
        </template>
        <template v-if="resultDetail.pytest_error_detail">
          <h4 style="margin-top: 12px">错误详情</h4>
          <pre style="background: #fff1f0; padding: 12px; border-radius: 4px; overflow: auto; max-height: 300px; font-size: 12px; color: #cf1322">{{ resultDetail.pytest_error_detail }}</pre>
        </template>
        <template v-if="resultDetail.error_message">
          <h4 style="margin-top: 12px">错误信息</h4>
          <a-alert :message="resultDetail.error_message" type="error" />
        </template>
      </template>
    </a-modal>

    <!-- 新建执行任务弹窗 -->
    <a-modal v-model:open="showModal" title="新建执行任务" @ok="handleSubmit" :confirmLoading="submitting" width="640px">
      <a-form :model="form" layout="vertical">
        <a-form-item label="任务名称" required><a-input v-model:value="form.name" placeholder="如: 用户接口回归测试" /></a-form-item>
        <a-form-item label="选择生成任务（需求）" required>
          <a-select v-model:value="form.generation_job_id" placeholder="选择已完成的接口测试生成任务" showSearch optionFilterProp="label" :options="genJobOptions" style="width: 100%" @change="onGenJobChange" />
          <div v-if="selectedGenJobInfo" style="margin-top: 8px; padding: 8px 12px; background: #f6ffed; border: 1px solid #b7eb8f; border-radius: 4px; font-size: 12px">
            <div><b>脚本用例数:</b> {{ selectedGenJobInfo.testcase_count }} 条</div>
            <div v-if="selectedGenJobInfo.requirement_name"><b>关联需求:</b> {{ selectedGenJobInfo.requirement_name }}</div>
          </div>
        </a-form-item>
        <a-form-item label="执行模式">
          <a-radio-group v-model:value="form.execution_mode">
            <a-radio value="pytest">pytest 脚本执行</a-radio>
            <a-radio value="httpx">内置引擎执行</a-radio>
          </a-radio-group>
          <div style="color: #999; font-size: 12px; margin-top: 4px">
            {{ form.execution_mode === 'pytest' ? 'pytest 模式：通过 AI 生成的 pytest 脚本执行测试，可在线查看和下载脚本' : 'httpx 模式：使用内置 HTTP 引擎直接发送请求执行测试' }}
          </div>
        </a-form-item>
        <a-divider>环境配置</a-divider>
        <a-row :gutter="16">
          <a-col :span="16"><a-form-item label="Base URL" required><a-input v-model:value="form.base_url" placeholder="http://localhost:8000" /></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="超时 (秒)"><a-input-number v-model:value="form.timeout" :min="1" :max="120" style="width: 100%" /></a-form-item></a-col>
        </a-row>
        <a-form-item label="全局 Headers (JSON)">
          <a-textarea v-model:value="form.headers_json" :rows="3" style="font-family: monospace" placeholder='{"Authorization": "Bearer xxx"}' />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import api from '../api'

const list = ref<any[]>([])
const loading = ref(false)
const statusFilter = ref<string | undefined>()
const showModal = ref(false)
const showResults = ref(false)
const showResultDetail = ref(false)
const submitting = ref(false)
const currentJob = ref<any>(null)
const resultDetail = ref<any>(null)
const results = ref<any[]>([])
const resultsLoading = ref(false)
const resultTab = ref('results')
const pytestScript = ref('')
const pagination = reactive({ current: 1, pageSize: 20, total: 0 })
const resultsPag = reactive({ current: 1, pageSize: 50, total: 0 })

const genJobOptions = ref<any[]>([])
const genJobMap = ref<Record<number, any>>({})
const selectedGenJobInfo = ref<any>(null)

const defaultHeaders = JSON.stringify({
  "Accept-Encoding": "gzip",
  "Content-Type": "application/json",
  "x-user-id": "xuser-df7f4883-986a-4b64-b797-455c6609c148",
  "x-sign-id": "f42a294454e5639932b1070324b86903",
  "device_id": "93d61a6764dabcbb"
}, null, 2)

const form = reactive({
  name: '', generation_job_id: null as number | null,
  execution_mode: 'pytest',
  base_url: 'https://test.xhey.top', timeout: 30, headers_json: defaultHeaders,
})

const statusLabels: Record<string, string> = { pending: '等待中', running: '运行中', success: '成功', failed: '失败', partial_fail: '部分失败' }
const statusColors: Record<string, string> = { pending: 'default', running: 'processing', success: 'success', failed: 'error', partial_fail: 'warning' }
const resultStatusLabels: Record<string, string> = { pass: '通过', fail: '失败', skip: '跳过', error: '异常', pending: '待执行' }

const columns = [
  { title: 'ID', dataIndex: 'id', width: 60 },
  { title: '任务名称', dataIndex: 'name', ellipsis: true },
  { title: '模式', key: 'exec_mode', width: 80 },
  { title: '状态', key: 'status', width: 100 },
  { title: '总用例', dataIndex: 'total_cases', width: 80 },
  { title: '执行结果', key: 'result', width: 220 },
  { title: '耗时', key: 'duration', width: 80 },
  { title: '创建时间', dataIndex: 'created_at', width: 170 },
  { title: '操作', key: 'actions', width: 150 },
]

const resultColumns = [
  { title: 'ID', dataIndex: 'id', width: 60 },
  { title: '用例ID', dataIndex: 'testcase_id', width: 70 },
  { title: '用例名称', dataIndex: 'testcase_title', ellipsis: true },
  { title: '状态', key: 'result_status', width: 80 },
  { title: '重试', dataIndex: 'retry_count', width: 60 },
  { title: '执行时间', dataIndex: 'executed_at', width: 170 },
  { title: '操作', key: 'result_actions', width: 80 },
]

const assertionResultColumns = [
  { title: '类型', dataIndex: 'type', width: 100 },
  { title: '路径', dataIndex: 'path' },
  { title: '期望', dataIndex: 'expected' },
  { title: '实际', dataIndex: 'actual' },
  { title: '结果', dataIndex: 'passed', customRender: ({ text }: any) => text ? '通过' : '失败' },
]

const loadData = async () => {
  loading.value = true
  const params: any = { page: pagination.current, page_size: pagination.pageSize }
  if (statusFilter.value) params.status = statusFilter.value
  try {
    const res: any = await api.get('/execution/jobs/', { params })
    list.value = res.data.items
    pagination.total = res.data.total
  } catch { /* ignore */ }
  loading.value = false
}

const onTableChange = (pag: any) => {
  pagination.current = pag.current
  loadData()
}

const loadGenJobOptions = async () => {
  try {
    const res: any = await api.get('/generation/jobs/', { params: { page: 1, page_size: 100, job_type: 'api', status: 'success' } })
    const items = res.data.items || []
    genJobMap.value = {}
    genJobOptions.value = items.map((gj: any) => {
      genJobMap.value[gj.id] = gj
      return {
        label: `#${gj.id} ${gj.name}`,
        value: gj.id,
      }
    })
  } catch { /* ignore */ }
}

const onGenJobChange = async (val: number) => {
  if (!val) {
    selectedGenJobInfo.value = null
    return
  }
  // 获取该生成任务下的用例数量
  try {
    const res: any = await api.get('/testcases/', { params: { page: 1, page_size: 1, generation_job_id: val, case_type: 'api' } })
    const gj = genJobMap.value[val]
    selectedGenJobInfo.value = {
      testcase_count: res.data.total || 0,
      requirement_name: gj?.requirement_content ? gj.requirement_content.substring(0, 50) : '',
    }
  } catch {
    selectedGenJobInfo.value = null
  }
}

const openCreate = () => {
  Object.assign(form, { name: '', generation_job_id: null, execution_mode: 'pytest', base_url: 'https://test.xhey.top', timeout: 30, headers_json: defaultHeaders })
  selectedGenJobInfo.value = null
  loadGenJobOptions()
  showModal.value = true
}

const handleSubmit = async () => {
  if (!form.name || !form.generation_job_id) { message.warning('请填写任务名称并选择生成任务'); return }
  let headers: Record<string, string> = {}
  if (form.headers_json.trim()) {
    try { headers = JSON.parse(form.headers_json) } catch { message.error('Headers JSON 格式无效'); return }
  }
  submitting.value = true
  try {
    await api.post('/execution/jobs/', {
      name: form.name,
      generation_job_id: form.generation_job_id,
      execution_mode: form.execution_mode,
      env_config: { base_url: form.base_url, timeout: form.timeout, headers },
    })
    message.success('执行任务已创建，后台运行中...')
    showModal.value = false
    loadData()
  } catch { message.error('创建失败') }
  submitting.value = false
}

const openResults = async (record: any) => {
  currentJob.value = record
  showResults.value = true
  resultTab.value = 'results'
  pytestScript.value = ''
  resultsPag.current = 1
  await loadResults(record.id)
  await loadPytestScript(record.id)
}

const loadResults = async (jobId: number) => {
  resultsLoading.value = true
  try {
    const res: any = await api.get(`/execution/jobs/${jobId}/results`, { params: { page: resultsPag.current, page_size: resultsPag.pageSize } })
    results.value = res.data.items
    resultsPag.total = res.data.total
  } catch { /* ignore */ }
  resultsLoading.value = false
}

const onResultsChange = (pag: any) => {
  resultsPag.current = pag.current
  if (currentJob.value) loadResults(currentJob.value.id)
}

const openResultDetail = (r: any) => {
  resultDetail.value = r
  showResultDetail.value = true
}

const loadPytestScript = async (jobId: number) => {
  try {
    const res: any = await api.get(`/execution/jobs/${jobId}/pytest-script`)
    pytestScript.value = res.data?.script_content || ''
  } catch {
    pytestScript.value = ''
  }
}

const downloadScript = () => {
  if (!pytestScript.value || !currentJob.value) return
  const blob = new Blob([pytestScript.value], { type: 'text/x-python' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `test_execution_${currentJob.value.id}.py`
  a.click()
  URL.revokeObjectURL(url)
}

const copyScript = () => {
  if (!pytestScript.value) return
  navigator.clipboard.writeText(pytestScript.value).then(() => {
    message.success('已复制到剪贴板')
  }).catch(() => {
    message.error('复制失败')
  })
}

const handleDownloadReport = (jobId: number) => {
  window.open(`/api/v1/execution/jobs/${jobId}/report`, '_blank')
}

onMounted(loadData)
</script>

<style scoped>
.code-block {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 16px;
  border-radius: 8px;
  overflow: auto;
  max-height: 500px;
  font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre;
  tab-size: 4;
}
</style>
