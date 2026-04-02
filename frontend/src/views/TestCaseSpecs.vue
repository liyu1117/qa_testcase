<template>
  <div>
    <div style="margin-bottom: 16px; display: flex; justify-content: space-between">
      <a-select v-model:value="typeFilter" placeholder="规范类型" style="width: 150px" allowClear @change="loadData">
        <a-select-option value="functional">功能测试</a-select-option>
        <a-select-option value="ui">UI测试</a-select-option>
        <a-select-option value="api">接口测试</a-select-option>
      </a-select>
      <a-button type="primary" @click="openCreate">新建规范</a-button>
    </div>

    <a-table :dataSource="list" :columns="columns" :loading="loading" rowKey="id" :pagination="false">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'spec_type'">
          <a-tag :color="typeColors[record.spec_type]">{{ typeLabels[record.spec_type] || record.spec_type }}</a-tag>
        </template>
        <template v-if="column.key === 'is_default'">
          <a-tag :color="record.is_default ? 'green' : 'default'">{{ record.is_default ? '默认' : '-' }}</a-tag>
        </template>
        <template v-if="column.key === 'updated_at'">
          {{ formatTime(record.updated_at) }}
        </template>
        <template v-if="column.key === 'actions'">
          <a-space>
            <a @click="openEdit(record)">编辑</a>
            <a-popconfirm title="确认删除?" @confirm="handleDelete(record.id)"><a style="color: red">删除</a></a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <a-modal v-model:open="showModal" :title="editId ? '编辑规范' : '新建规范'" @ok="handleSubmit" :confirmLoading="submitting" width="800px">
      <a-form :model="form" layout="vertical">
        <a-form-item label="名称" required><a-input v-model:value="form.name" /></a-form-item>
        <a-form-item label="类型" required>
          <a-select v-model:value="form.spec_type">
            <a-select-option value="functional">功能测试</a-select-option>
            <a-select-option value="ui">UI测试</a-select-option>
            <a-select-option value="api">接口测试</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="设为默认"><a-switch v-model:checked="form.is_default" /></a-form-item>
        <a-form-item label="规范内容 (Markdown)">
          <a-textarea v-model:value="form.content" :rows="15" style="font-family: monospace" />
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
const typeFilter = ref<string | undefined>()
const showModal = ref(false)
const submitting = ref(false)
const editId = ref<number | null>(null)
const form = reactive({ name: '', spec_type: 'functional', content: '', is_default: false })

const typeLabels: Record<string, string> = { functional: '功能测试', ui: 'UI测试', api: '接口测试' }
const typeColors: Record<string, string> = { functional: 'blue', ui: 'purple', api: 'green' }

const formatTime = (t: string) => {
  if (!t) return '-'
  return t.replace('T', ' ').substring(0, 19)
}

const columns = [
  { title: 'ID', dataIndex: 'id', width: 60 },
  { title: '名称', dataIndex: 'name' },
  { title: '类型', key: 'spec_type', width: 100 },
  { title: '默认', key: 'is_default', width: 80 },
  { title: '更新时间', key: 'updated_at', width: 180 },
  { title: '操作', key: 'actions', width: 120 },
]

const loadData = async () => {
  loading.value = true
  const params: any = { page: 1, page_size: 100 }
  if (typeFilter.value) params.spec_type = typeFilter.value
  const res: any = await api.get('/specs/', { params })
  list.value = res.data.items
  loading.value = false
}

const openCreate = () => {
  editId.value = null
  Object.assign(form, { name: '', spec_type: 'functional', content: '', is_default: false })
  showModal.value = true
}

const openEdit = (record: any) => {
  editId.value = record.id
  Object.assign(form, { name: record.name, spec_type: record.spec_type, content: record.content, is_default: record.is_default })
  showModal.value = true
}

const handleSubmit = async () => {
  if (!form.name || !form.content) { message.warning('请填写完整'); return }
  submitting.value = true
  if (editId.value) {
    await api.put(`/specs/${editId.value}`, form)
    message.success('更新成功')
  } else {
    await api.post('/specs/', form)
    message.success('创建成功')
  }
  submitting.value = false
  showModal.value = false
  loadData()
}

const handleDelete = async (id: number) => {
  await api.delete(`/specs/${id}`)
  message.success('删除成功')
  loadData()
}

onMounted(loadData)
</script>
