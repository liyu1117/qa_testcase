<template>
  <div>
    <div style="margin-bottom: 16px; display: flex; justify-content: space-between">
      <a-space>
        <a-select v-model:value="typeFilter" placeholder="任务类型" style="width: 120px" allowClear @change="loadData">
          <a-select-option value="functional">功能测试</a-select-option>
          <a-select-option value="ui">UI测试</a-select-option>
          <a-select-option value="api">接口测试</a-select-option>
        </a-select>
        <a-select v-model:value="statusFilter" placeholder="状态" style="width: 120px" allowClear @change="loadData">
          <a-select-option value="pending">等待中</a-select-option>
          <a-select-option value="running">运行中</a-select-option>
          <a-select-option value="success">成功</a-select-option>
          <a-select-option value="failed">失败</a-select-option>
        </a-select>
      </a-space>
      <a-button type="primary" @click="openCreate">新建生成任务</a-button>
    </div>

    <a-table :dataSource="list" :columns="columns" :loading="loading" :pagination="pagination" @change="onTableChange" rowKey="id" size="middle">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'job_type'">
          <a-tag :color="typeColors[record.job_type]">{{ typeLabels[record.job_type] }}</a-tag>
        </template>
        <template v-if="column.key === 'status'">
          <a-tag :color="statusColors[record.status]">{{ statusLabels[record.status] }}</a-tag>
        </template>
        <template v-if="column.key === 'progress'">
          <a-progress :percent="record.progress" :status="record.status === 'failed' ? 'exception' : record.progress === 100 ? 'success' : 'active'" size="small" />
        </template>
        <template v-if="column.key === 'actions'">
          <a-space>
            <a @click="openDetail(record)">详情</a>
            <a-dropdown v-if="record.result_file_path">
              <a>下载并上传 <DownOutlined /></a>
              <template #overlay>
                <a-menu @click="({ key }: any) => handleDownload(record.id, key as 'md' | 'xmind')">
                  <a-menu-item key="md">下载并上传 Markdown</a-menu-item>
                  <a-menu-item key="xmind">下载并上传 XMind</a-menu-item>
                </a-menu>
              </template>
            </a-dropdown>
          </a-space>
        </template>
      </template>
    </a-table>

    <!-- 详情抽屉 -->
    <a-drawer v-model:open="showDetail" title="生成任务详情" width="660">
      <template v-if="detailRecord">
        <a-descriptions :column="1" bordered size="small">
          <a-descriptions-item label="ID">{{ detailRecord.id }}</a-descriptions-item>
          <a-descriptions-item label="任务名称">{{ detailRecord.name }}</a-descriptions-item>
          <a-descriptions-item label="任务类型">{{ typeLabels[detailRecord.job_type] }}</a-descriptions-item>
          <a-descriptions-item label="关联需求ID">{{ detailRecord.requirement_id }}</a-descriptions-item>
          <a-descriptions-item label="规范ID">{{ detailRecord.spec_id || '-' }}</a-descriptions-item>
          <a-descriptions-item label="AI模型">{{ detailRecord.ai_model || '默认' }}</a-descriptions-item>
          <a-descriptions-item label="状态">
            <a-tag :color="statusColors[detailRecord.status]">{{ statusLabels[detailRecord.status] }}</a-tag>
            <span v-if="detailRecord.status === 'success' && detailCaseCount === 0" style="color: #faad14; margin-left: 8px; font-size: 12px">⚠ 生成成功但解析到 0 条用例</span>
          </a-descriptions-item>
          <a-descriptions-item label="生成用例数">
            <span :style="{ color: detailCaseCount > 0 ? '#52c41a' : '#ff4d4f', fontWeight: 'bold' }">{{ detailCaseCount }} 条</span>
          </a-descriptions-item>
          <a-descriptions-item label="进度">
            <a-progress :percent="detailRecord.progress" size="small" />
          </a-descriptions-item>
          <a-descriptions-item label="开始时间">{{ detailRecord.started_at || '-' }}</a-descriptions-item>
          <a-descriptions-item label="完成时间">{{ detailRecord.finished_at || '-' }}</a-descriptions-item>
          <a-descriptions-item label="创建时间">{{ detailRecord.created_at }}</a-descriptions-item>
          <a-descriptions-item v-if="detailRecord.error_message" label="错误信息">
            <span style="color: red">{{ detailRecord.error_message }}</span>
          </a-descriptions-item>
          <a-descriptions-item v-if="detailRecord.figma_url" label="Figma URL">
            <a :href="detailRecord.figma_url" target="_blank" style="word-break: break-all; font-size: 12px">{{ detailRecord.figma_url }}</a>
          </a-descriptions-item>
          <a-descriptions-item v-if="detailRecord.yapi_project_id" label="YApi Project">{{ detailRecord.yapi_project_id }}</a-descriptions-item>
          <a-descriptions-item v-if="detailRecord.yapi_interface_paths?.length" label="指定接口">
            <a-tag v-for="p in detailRecord.yapi_interface_paths" :key="p" style="margin-bottom: 4px">{{ p }}</a-tag>
          </a-descriptions-item>
        </a-descriptions>

        <!-- Figma 设计稿信息（仅 UI 类型） -->
        <div v-if="detailRecord.job_type === 'ui' && detailRecord.figma_url" style="margin-top: 16px">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px">
            <h4 style="margin: 0">Figma 设计稿读取信息</h4>
            <a-button size="small" @click="showFigmaInfo = !showFigmaInfo">{{ showFigmaInfo ? '收起' : '展开' }}</a-button>
          </div>
          <div v-if="showFigmaInfo">
            <div v-if="figmaDesignDesc" style="background: #f6ffed; border: 1px solid #b7eb8f; border-radius: 6px; padding: 12px; max-height: 300px; overflow-y: auto; white-space: pre-wrap; font-size: 12px; line-height: 1.6">{{ figmaDesignDesc }}</div>
            <a-empty v-else description="未读取到 Figma 设计稿信息（可能获取失败或未配置 Figma Token）" />
          </div>
        </div>

        <div v-if="detailRecord.requirement_content" style="margin-top: 16px">
          <h4 style="margin-bottom: 8px">读取到的需求内容</h4>
          <div style="background: #f5f5f5; border-radius: 6px; padding: 12px; max-height: 400px; overflow-y: auto; white-space: pre-wrap; font-size: 13px; line-height: 1.6; border: 1px solid #e8e8e8;">{{ detailRecord.requirement_content }}</div>
        </div>
        <div v-if="detailRecord.yapi_doc_content" style="margin-top: 16px">
          <h4 style="margin-bottom: 8px">YApi 接口文档</h4>
          <div style="background: #f5f5f5; border-radius: 6px; padding: 12px; max-height: 400px; overflow-y: auto; white-space: pre-wrap; font-size: 13px; line-height: 1.6; border: 1px solid #e8e8e8;">{{ detailRecord.yapi_doc_content }}</div>
        </div>

        <!-- AI 原始输出 -->
        <div v-if="detailRecord.raw_output" style="margin-top: 16px">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px">
            <h4 style="margin: 0">AI 原始输出</h4>
            <a-button size="small" @click="showRawOutput = !showRawOutput">{{ showRawOutput ? '收起' : '展开' }}</a-button>
          </div>
          <div v-if="showRawOutput" style="background: #1e1e1e; color: #d4d4d4; border-radius: 6px; padding: 12px; max-height: 500px; overflow-y: auto; white-space: pre-wrap; font-size: 12px; line-height: 1.6; font-family: 'Menlo', 'Monaco', 'Courier New', monospace;">{{ detailRecord.raw_output }}</div>
        </div>
      </template>
    </a-drawer>

    <!-- 新建弹窗 -->
    <a-modal v-model:open="showModal" title="新建生成任务" @ok="handleSubmit" :confirmLoading="submitting" width="600px">
      <a-form :model="form" layout="vertical">
        <a-form-item label="任务名称" required><a-input v-model:value="form.name" placeholder="如: 登录模块功能测试" /></a-form-item>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="任务类型" required>
              <a-select v-model:value="form.job_type" @change="onJobTypeChange">
                <a-select-option value="functional">功能测试</a-select-option>
                <a-select-option value="ui">UI测试</a-select-option>
                <a-select-option value="api">接口测试</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="关联需求" required>
              <a-select v-model:value="form.requirement_id" placeholder="选择需求" showSearch optionFilterProp="label" :options="requirementOptions" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item label="用例规范">
          <a-select v-model:value="form.spec_id" placeholder="选择规范（可选，不选择则使用默认）" allowClear :options="specOptions" />
        </a-form-item>
        <a-form-item v-if="form.job_type === 'ui'" label="Figma 文件 URL">
          <a-input v-model:value="form.figma_url" placeholder="https://www.figma.com/file/..." />
        </a-form-item>
        <a-form-item v-if="form.job_type === 'api'" label="YApi 项目 ID">
          <a-input v-model:value="form.yapi_project_id" placeholder="YApi 项目编号" />
        </a-form-item>
        <a-form-item v-if="form.job_type === 'api'" label="YApi 项目 Token">
          <a-input v-model:value="form.yapi_token" placeholder="YApi 项目的访问 Token（在 YApi 项目设置中获取）" />
        </a-form-item>
        <a-form-item v-if="form.job_type === 'api'" label="指定接口路径（可选）">
          <a-textarea v-model:value="form.yapi_interface_paths_text" placeholder="每行一个接口路径，如：&#10;/api/v1/auth/login&#10;/api/v1/user/profile&#10;&#10;留空则获取项目全部接口" :rows="4" />
        </a-form-item>
        <a-form-item label="AI 模型">
          <a-select v-model:value="form.ai_model" placeholder="使用默认模型" allowClear>
            <a-select-option value="chat-pro">chat-pro</a-select-option>
            <a-select-option value="code-pro">code-pro</a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { message, Modal} from 'ant-design-vue'
import { DownOutlined } from '@ant-design/icons-vue'
import api from '../api'

const list = ref<any[]>([])
const loading = ref(false)
const typeFilter = ref<string | undefined>()
const statusFilter = ref<string | undefined>()
const showModal = ref(false)
const showDetail = ref(false)
const submitting = ref(false)
const detailRecord = ref<any>(null)
const detailCaseCount = ref(0)
const showFigmaInfo = ref(false)
const showRawOutput = ref(false)
const figmaDesignDesc = ref('')
const pagination = reactive({ current: 1, pageSize: 20, total: 0 })

const requirementOptions = ref<any[]>([])
const specOptions = ref<any[]>([])

const form = reactive({
  name: '', job_type: 'functional', requirement_id: undefined as number | undefined,
  spec_id: undefined as number | undefined, figma_url: '', yapi_project_id: '', yapi_token: '', yapi_interface_paths_text: '', ai_model: undefined as string | undefined,
})

const typeLabels: Record<string, string> = { functional: '功能测试', ui: 'UI测试', api: '接口测试' }
const typeColors: Record<string, string> = { functional: 'blue', ui: 'purple', api: 'green' }
const statusLabels: Record<string, string> = { pending: '等待中', running: '运行中', success: '成功', failed: '失败' }
const statusColors: Record<string, string> = { pending: 'default', running: 'processing', success: 'success', failed: 'error' }

const columns = [
  { title: 'ID', dataIndex: 'id', width: 60 },
  { title: '任务名称', dataIndex: 'name', ellipsis: true },
  { title: '类型', key: 'job_type', width: 100 },
  { title: '状态', key: 'status', width: 100 },
  { title: '进度', key: 'progress', width: 160 },
  { title: '需求ID', dataIndex: 'requirement_id', width: 80 },
  { title: '创建时间', dataIndex: 'created_at', width: 170 },
  { title: '操作', key: 'actions', width: 120 },
]

const loadData = async () => {
  loading.value = true
  const params: any = { page: pagination.current, page_size: pagination.pageSize }
  if (typeFilter.value) params.job_type = typeFilter.value
  if (statusFilter.value) params.status = statusFilter.value
  try {
    const res: any = await api.get('/generation/jobs/', { params })
    list.value = res.data.items
    pagination.total = res.data.total
  } catch { /* ignore */ }
  loading.value = false
}

const loadOptions = async () => {
  try {
    const [reqRes, specRes]: any[] = await Promise.all([
      api.get('/requirements/', { params: { page: 1, page_size: 100 } }),
      api.get('/specs/', { params: { page: 1, page_size: 100 } }),
    ])
    requirementOptions.value = reqRes.data.items.map((r: any) => ({ label: `#${r.id} ${r.title}`, value: r.id }))
    specOptions.value = specRes.data.items.map((s: any) => ({ label: `${s.name} (${typeLabels[s.spec_type] || s.spec_type})`, value: s.id }))
  } catch { /* ignore */ }
}

const onTableChange = (pag: any) => {
  pagination.current = pag.current
  loadData()
}

const openCreate = () => {
  Object.assign(form, { name: '', job_type: 'functional', requirement_id: undefined, spec_id: undefined, figma_url: '', yapi_project_id: '', yapi_token: '', yapi_interface_paths_text: '', ai_model: undefined })
  loadOptions()
  showModal.value = true
}

const onJobTypeChange = () => {
  form.figma_url = ''
  form.yapi_project_id = ''
  form.yapi_token = ''
  form.yapi_interface_paths_text = ''
}

const openDetail = async (record: any) => {
  try {
    const res: any = await api.get(`/generation/jobs/${record.id}`)
    detailRecord.value = res.data
  } catch {
    detailRecord.value = record
  }

  // 获取该任务生成的用例数量
  detailCaseCount.value = 0
  try {
    const caseRes: any = await api.get('/testcases/', { params: { generation_job_id: record.id, page: 1, page_size: 1 } })
    detailCaseCount.value = caseRes.data.total || 0
  } catch { /* ignore */ }

  // 从 requirement_content 中分离 Figma 信息
  figmaDesignDesc.value = ''
  if (detailRecord.value?.requirement_content) {
    const content = detailRecord.value.requirement_content as string
    const figmaSep = '---\n\n## Figma 设计稿读取信息\n\n'
    const sepIdx = content.indexOf(figmaSep)
    if (sepIdx >= 0) {
      figmaDesignDesc.value = content.substring(sepIdx + figmaSep.length).trim()
      // 将纯需求内容回写供展示
      detailRecord.value.requirement_content = content.substring(0, sepIdx).trim() || null
    }
  }

  showFigmaInfo.value = false
  showRawOutput.value = false
  showDetail.value = true
}

const handleSubmit = async () => {
  if (!form.name || !form.requirement_id) { message.warning('请填写必要信息'); return }
  submitting.value = true
  try {
    const payload: any = { name: form.name, job_type: form.job_type, requirement_id: form.requirement_id }
    if (form.spec_id) payload.spec_id = form.spec_id
    if (form.ai_model) payload.ai_model = form.ai_model
    if (form.job_type === 'ui' && form.figma_url) payload.figma_url = form.figma_url
    if (form.job_type === 'api' && form.yapi_project_id) {
      payload.yapi_project_id = form.yapi_project_id
      if (form.yapi_token) payload.yapi_token = form.yapi_token
      if (form.yapi_interface_paths_text.trim()) {
        payload.yapi_interface_paths = form.yapi_interface_paths_text.split('\n').map((p: string) => p.trim()).filter((p: string) => p)
      }
    }
    await api.post('/generation/jobs/', payload)
    message.success('生成任务已创建，后台执行中...')
    showModal.value = false
    loadData()
  } catch { message.error('创建失败') }
  submitting.value = false
}

const handleDownload = async (jobId: number, format: 'md' | 'xmind' = 'md') => {
  try {
    // 1. 先上传到钉钉
    const uploadRes: any = await api.post(`/generation/jobs/${jobId}/upload`, null, {
      params: { format }
    })

    const dingtalkUrl = uploadRes?.data?.dingtalk_url || ''

    if (dingtalkUrl) {
      Modal.confirm({
        title: '上传到钉钉成功',
        content: '文件已上传到钉钉，是否立即打开？',
        okText: '打开钉钉',
        cancelText: '稍后',
        onOk() {
          window.open(dingtalkUrl, '_blank')
        },
      })
    } else {
      message.success('上传到钉钉成功')
    }

    // 2. 再触发下载
    window.open(`/api/v1/generation/jobs/${jobId}/download?format=${format}`, '_blank')
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '上传到钉钉失败')
  }
}

onMounted(loadData)
</script>
