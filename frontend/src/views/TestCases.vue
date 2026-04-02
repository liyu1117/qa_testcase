<template>
  <div>
    <div style="margin-bottom: 16px; display: flex; justify-content: space-between">
      <a-space>
        <a-input-search v-model:value="keyword" placeholder="搜索用例标题" @search="loadData" style="width: 200px" allowClear />
        <a-select v-model:value="typeFilter" placeholder="用例类型" style="width: 120px" allowClear @change="loadData">
          <a-select-option value="functional">功能测试</a-select-option>
          <a-select-option value="ui">UI测试</a-select-option>
          <a-select-option value="api">接口测试</a-select-option>
        </a-select>
        <a-select v-model:value="priorityFilter" placeholder="优先级" style="width: 100px" allowClear @change="loadData">
          <a-select-option value="P0">P0</a-select-option>
          <a-select-option value="P1">P1</a-select-option>
          <a-select-option value="P2">P2</a-select-option>
          <a-select-option value="P3">P3</a-select-option>
        </a-select>
        <a-select v-model:value="statusFilter" placeholder="状态" style="width: 100px" allowClear @change="loadData">
          <a-select-option value="draft">草稿</a-select-option>
          <a-select-option value="active">启用</a-select-option>
          <a-select-option value="deprecated">废弃</a-select-option>
        </a-select>
      </a-space>
      <a-space>
        <a-button @click="handleExport">导出 Markdown</a-button>
        <a-button type="primary" @click="openCreate">新建用例</a-button>
      </a-space>
    </div>

    <a-table :dataSource="list" :columns="columns" :loading="loading" :pagination="pagination" @change="onTableChange" rowKey="id" size="middle">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'case_type'">
          <a-tag :color="typeColors[record.case_type]">{{ typeLabels[record.case_type] || record.case_type }}</a-tag>
        </template>
        <template v-if="column.key === 'priority'">
          <a-tag :color="priorityColors[record.priority]">{{ record.priority }}</a-tag>
        </template>
        <template v-if="column.key === 'status'">
          <a-tag :color="statusColors[record.status]">{{ statusLabels[record.status] || record.status }}</a-tag>
        </template>
        <template v-if="column.key === 'created_at'">
          {{ formatTime(record.created_at) }}
        </template>
        <template v-if="column.key === 'actions'">
          <a-space>
            <a @click="openDetail(record)">查看</a>
            <a @click="openEdit(record)">编辑</a>
            <a-popconfirm title="确认删除?" @confirm="handleDelete(record.id)"><a style="color: red">删除</a></a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <!-- 详情抽屉 -->
    <a-drawer v-model:open="showDetail" title="用例详情" width="640">
      <template v-if="detailRecord">
        <a-descriptions :column="2" bordered size="small">
          <a-descriptions-item label="ID">{{ detailRecord.id }}</a-descriptions-item>
          <a-descriptions-item label="标题">{{ detailRecord.title }}</a-descriptions-item>
          <a-descriptions-item label="类型">{{ typeLabels[detailRecord.case_type] }}</a-descriptions-item>
          <a-descriptions-item label="优先级">{{ detailRecord.priority }}</a-descriptions-item>
          <a-descriptions-item label="模块">{{ detailRecord.module || '-' }}</a-descriptions-item>
          <a-descriptions-item label="状态">{{ statusLabels[detailRecord.status] }}</a-descriptions-item>
          <a-descriptions-item label="需求ID">{{ detailRecord.requirement_id || '-' }}</a-descriptions-item>
          <a-descriptions-item label="生成任务ID">{{ detailRecord.generation_job_id || '-' }}</a-descriptions-item>
        </a-descriptions>
        <template v-if="detailRecord.precondition">
          <h4 style="margin-top: 16px">前置条件</h4>
          <p>{{ detailRecord.precondition }}</p>
        </template>
        <template v-if="detailRecord.steps?.length">
          <h4 style="margin-top: 16px">测试步骤</h4>
          <a-table :dataSource="detailRecord.steps" :columns="stepColumns" :pagination="false" size="small" rowKey="step" />
        </template>
        <template v-if="detailRecord.expected_result">
          <h4 style="margin-top: 16px">预期结果</h4>
          <p>{{ detailRecord.expected_result }}</p>
        </template>
        <template v-if="detailRecord.case_type === 'api'">
          <h4 style="margin-top: 16px">接口信息</h4>
          <a-descriptions :column="2" bordered size="small">
            <a-descriptions-item label="Method">{{ detailRecord.api_method }}</a-descriptions-item>
            <a-descriptions-item label="Path">{{ detailRecord.api_path }}</a-descriptions-item>
          </a-descriptions>
          <template v-if="detailRecord.api_assertions?.length">
            <h4 style="margin-top: 12px">断言规则</h4>
            <a-table :dataSource="detailRecord.api_assertions" :columns="assertionColumns" :pagination="false" size="small" />
          </template>
        </template>
      </template>
    </a-drawer>

    <!-- 新建/编辑弹窗 -->
    <a-modal v-model:open="showModal" :title="editId ? '编辑用例' : '新建用例'" @ok="handleSubmit" :confirmLoading="submitting" width="720px">
      <a-form :model="form" layout="vertical">
        <a-row :gutter="16">
          <a-col :span="16"><a-form-item label="标题" required><a-input v-model:value="form.title" /></a-form-item></a-col>
          <a-col :span="8">
            <a-form-item label="类型" required>
              <a-select v-model:value="form.case_type">
                <a-select-option value="functional">功能测试</a-select-option>
                <a-select-option value="ui">UI测试</a-select-option>
                <a-select-option value="api">接口测试</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>
        <a-row :gutter="16">
          <a-col :span="8"><a-form-item label="优先级"><a-select v-model:value="form.priority"><a-select-option v-for="p in ['P0','P1','P2','P3']" :key="p" :value="p">{{ p }}</a-select-option></a-select></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="模块"><a-input v-model:value="form.module" /></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="状态"><a-select v-model:value="form.status"><a-select-option value="draft">草稿</a-select-option><a-select-option value="active">启用</a-select-option><a-select-option value="deprecated">废弃</a-select-option></a-select></a-form-item></a-col>
        </a-row>
        <a-form-item label="前置条件"><a-textarea v-model:value="form.precondition" :rows="2" /></a-form-item>
        <a-form-item label="预期结果"><a-textarea v-model:value="form.expected_result" :rows="2" /></a-form-item>
        <template v-if="form.case_type === 'api'">
          <a-row :gutter="16">
            <a-col :span="6"><a-form-item label="Method"><a-select v-model:value="form.api_method"><a-select-option v-for="m in ['GET','POST','PUT','DELETE','PATCH']" :key="m" :value="m">{{ m }}</a-select-option></a-select></a-form-item></a-col>
            <a-col :span="18"><a-form-item label="Path"><a-input v-model:value="form.api_path" placeholder="/api/v1/xxx" /></a-form-item></a-col>
          </a-row>
        </template>
        <a-form-item label="Markdown 内容"><a-textarea v-model:value="form.content_md" :rows="6" style="font-family: monospace" /></a-form-item>
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
const keyword = ref('')
const typeFilter = ref<string | undefined>()
const priorityFilter = ref<string | undefined>()
const statusFilter = ref<string | undefined>()
const showModal = ref(false)
const showDetail = ref(false)
const submitting = ref(false)
const editId = ref<number | null>(null)
const detailRecord = ref<any>(null)
const pagination = reactive({ current: 1, pageSize: 20, total: 0 })

const form = reactive({
  title: '', case_type: 'functional', priority: 'P2', module: '',
  precondition: '', expected_result: '', content_md: '', status: 'draft',
  api_method: 'GET', api_path: '',
})

const typeLabels: Record<string, string> = { functional: '功能测试', ui: 'UI测试', api: '接口测试' }
const typeColors: Record<string, string> = { functional: 'blue', ui: 'purple', api: 'green' }
const priorityColors: Record<string, string> = { P0: 'red', P1: 'orange', P2: 'blue', P3: 'default' }
const statusLabels: Record<string, string> = { draft: '草稿', active: '启用', deprecated: '废弃' }
const statusColors: Record<string, string> = { draft: 'default', active: 'green', deprecated: 'red' }

const columns = [
  { title: 'ID', dataIndex: 'id', width: 60 },
  { title: '标题', dataIndex: 'title', ellipsis: true },
  { title: '类型', key: 'case_type', width: 100 },
  { title: '优先级', key: 'priority', width: 80 },
  { title: '模块', dataIndex: 'module', width: 120, ellipsis: true },
  { title: '状态', key: 'status', width: 80 },
  { title: '创建时间', key: 'created_at', width: 170 },
  { title: '操作', key: 'actions', width: 150 },
]

const stepColumns = [
  { title: '步骤', dataIndex: 'step', width: 60 },
  { title: '操作', dataIndex: 'action' },
  { title: '预期', dataIndex: 'expected' },
]

const assertionColumns = [
  { title: '类型', dataIndex: 'type', width: 100 },
  { title: '路径', dataIndex: 'path' },
  { title: '期望值', dataIndex: 'expected' },
  { title: '操作符', dataIndex: 'operator', width: 80 },
]

const loadData = async () => {
  loading.value = true
  const params: any = { page: pagination.current, page_size: pagination.pageSize }
  if (keyword.value) params.keyword = keyword.value
  if (typeFilter.value) params.case_type = typeFilter.value
  if (priorityFilter.value) params.priority = priorityFilter.value
  if (statusFilter.value) params.status = statusFilter.value
  try {
    const res: any = await api.get('/testcases/', { params })
    list.value = res.data.items
    pagination.total = res.data.total
  } catch { /* ignore */ }
  loading.value = false
}

const onTableChange = (pag: any) => {
  pagination.current = pag.current
  loadData()
}

const openCreate = () => {
  editId.value = null
  Object.assign(form, {
    title: '', case_type: 'functional', priority: 'P2', module: '',
    precondition: '', expected_result: '', content_md: '', status: 'draft',
    api_method: 'GET', api_path: '',
  })
  showModal.value = true
}

const openEdit = (record: any) => {
  editId.value = record.id
  Object.assign(form, {
    title: record.title, case_type: record.case_type, priority: record.priority,
    module: record.module || '', precondition: record.precondition || '',
    expected_result: record.expected_result || '', content_md: record.content_md || '',
    status: record.status, api_method: record.api_method || 'GET', api_path: record.api_path || '',
  })
  showModal.value = true
}

const openDetail = (record: any) => {
  detailRecord.value = record
  showDetail.value = true
}

const handleSubmit = async () => {
  if (!form.title) { message.warning('请输入标题'); return }
  submitting.value = true
  try {
    const payload: any = { ...form }
    if (form.case_type !== 'api') {
      delete payload.api_method
      delete payload.api_path
    }
    if (editId.value) {
      await api.put(`/testcases/${editId.value}`, payload)
      message.success('更新成功')
    } else {
      await api.post('/testcases/', payload)
      message.success('创建成功')
    }
    showModal.value = false
    loadData()
  } catch { message.error('操作失败') }
  submitting.value = false
}

const handleDelete = async (id: number) => {
  await api.delete(`/testcases/${id}`)
  message.success('删除成功')
  loadData()
}

const handleExport = () => {
  const params = new URLSearchParams()
  if (typeFilter.value) params.set('case_type', typeFilter.value)
  window.open(`/api/v1/testcases/export?${params.toString()}`, '_blank')
}

onMounted(loadData)

const formatTime = (t: string) => {
  if (!t) return '-'
  return t.replace('T', ' ').replace(/\.\d+$/, '')
}
</script>
