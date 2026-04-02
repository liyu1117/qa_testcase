<template>
  <div>
    <div style="margin-bottom: 16px; display: flex; justify-content: space-between">
      <a-space>
        <a-input-search v-model:value="keyword" placeholder="搜索需求" @search="loadData" style="width: 250px" allowClear />
        <a-select v-model:value="statusFilter" placeholder="状态" style="width: 120px" allowClear @change="loadData">
          <a-select-option value="pending">待处理</a-select-option>
          <a-select-option value="in_generation">生成中</a-select-option>
          <a-select-option value="done">已完成</a-select-option>
        </a-select>
      </a-space>
      <a-button type="primary" @click="openCreate">新建需求</a-button>
    </div>

    <a-table :dataSource="list" :columns="columns" :loading="loading" :pagination="pagination" @change="onTableChange" rowKey="id">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <a-tag :color="statusColors[record.status]">{{ statusLabels[record.status] || record.status }}</a-tag>
        </template>
        <template v-if="column.key === 'created_at'">
          {{ formatTime(record.created_at) }}
        </template>
        <template v-if="column.key === 'actions'">
          <a-space>
            <a @click="openEdit(record)">编辑</a>
            <a-popconfirm title="确认删除?" @confirm="handleDelete(record.id)"><a style="color: red">删除</a></a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <a-modal v-model:open="showModal" :title="editId ? '编辑需求' : '新建需求'" @ok="handleSubmit" :confirmLoading="submitting">
      <a-form :model="form" layout="vertical">
        <a-form-item label="标题" required><a-input v-model:value="form.title" /></a-form-item>
        <a-form-item label="描述"><a-textarea v-model:value="form.description" :rows="4" /></a-form-item>
        <a-form-item label="钉钉文档链接"><a-input v-model:value="form.source_url" placeholder="https://..." /></a-form-item>
        <a-form-item label="负责人"><a-input v-model:value="form.assignee" /></a-form-item>
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
const statusFilter = ref<string | undefined>()
const showModal = ref(false)
const submitting = ref(false)
const editId = ref<number | null>(null)
const pagination = reactive({ current: 1, pageSize: 20, total: 0 })

const form = reactive({ title: '', description: '', source_url: '', assignee: '' })

const statusLabels: Record<string, string> = { pending: '待处理', in_generation: '生成中', done: '已完成' }
const statusColors: Record<string, string> = { pending: 'default', in_generation: 'processing', done: 'success' }

const columns = [
  { title: 'ID', dataIndex: 'id', width: 60 },
  { title: '标题', dataIndex: 'title', ellipsis: true },
  { title: '状态', key: 'status', width: 100 },
  { title: '负责人', dataIndex: 'assignee', width: 100 },
  { title: '创建时间', key: 'created_at', width: 180 },
  { title: '操作', key: 'actions', width: 150 },
]

const formatTime = (t: string) => {
  if (!t) return '-'
  return t.replace('T', ' ').substring(0, 19)
}

const loadData = async () => {
  loading.value = true
  const params: any = { page: pagination.current, page_size: pagination.pageSize }
  if (keyword.value) params.keyword = keyword.value
  if (statusFilter.value) params.status = statusFilter.value
  try {
    const res: any = await api.get('/requirements/', { params })
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
  Object.assign(form, { title: '', description: '', source_url: '', assignee: '' })
  showModal.value = true
}

const openEdit = (record: any) => {
  editId.value = record.id
  Object.assign(form, {
    title: record.title || '', description: record.description || '',
    source_url: record.source_url || '', assignee: record.assignee || '',
  })
  showModal.value = true
}

const handleSubmit = async () => {
  if (!form.title) { message.warning('请输入标题'); return }
  submitting.value = true
  try {
    if (editId.value) {
      await api.put(`/requirements/${editId.value}`, form)
      message.success('更新成功')
    } else {
      await api.post('/requirements/', form)
      message.success('创建成功')
    }
    showModal.value = false
    editId.value = null
    Object.assign(form, { title: '', description: '', source_url: '', assignee: '' })
    loadData()
  } catch { message.error('操作失败') }
  submitting.value = false
}

const handleDelete = async (id: number) => {
  try {
    await api.delete(`/requirements/${id}`)
    message.success('删除成功')
    loadData()
  } catch { message.error('删除失败') }
}

onMounted(loadData)
</script>
