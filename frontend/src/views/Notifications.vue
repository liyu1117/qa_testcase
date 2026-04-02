<template>
  <div>
    <!-- 通知配置 -->
    <a-card title="钉钉通知配置" style="margin-bottom: 24px">
      <a-form :model="config" layout="vertical" style="max-width: 600px">
        <a-form-item label="Webhook URL">
          <a-input v-model:value="config.dingtalk_webhook_url" placeholder="https://oapi.dingtalk.com/robot/send?access_token=..." />
        </a-form-item>
        <a-form-item label="签名密钥 (Secret)">
          <a-input-password v-model:value="config.dingtalk_webhook_secret" placeholder="SEC..." />
        </a-form-item>
        <a-form-item label="启用通知">
          <a-switch v-model:checked="config.enabled" />
        </a-form-item>
        <a-form-item>
          <a-space>
            <a-button type="primary" @click="saveConfig" :loading="savingConfig">保存配置</a-button>
            <a-button @click="testSend" :loading="testingSend">测试发送</a-button>
          </a-space>
        </a-form-item>
      </a-form>
    </a-card>

    <!-- 通知日志 -->
    <a-card title="通知记录">
      <div style="margin-bottom: 16px">
        <a-select v-model:value="eventTypeFilter" placeholder="事件类型" style="width: 200px" allowClear @change="loadLogs">
          <a-select-option value="generation_done">生成完成</a-select-option>
          <a-select-option value="generation_failed">生成失败</a-select-option>
          <a-select-option value="execution_done">执行完成</a-select-option>
          <a-select-option value="execution_failed">执行失败</a-select-option>
          <a-select-option value="upload_done">上传成功</a-select-option>
        </a-select>
      </div>

      <a-table :dataSource="logs" :columns="logColumns" :loading="logsLoading" :pagination="logsPag" @change="onLogsChange" rowKey="id" size="middle">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'event_type'">
            <a-tag :color="eventTypeColors[record.event_type]">{{ eventTypeLabels[record.event_type] || record.event_type }}</a-tag>
          </template>
          <template v-if="column.key === 'log_status'">
            <a-tag :color="record.status === 'success' ? 'green' : record.status === 'failed' ? 'red' : 'default'">{{ record.status }}</a-tag>
          </template>
          <template v-if="column.key === 'message_body'">
            <a-tooltip :title="record.message_body"><span>{{ record.message_body?.substring(0, 60) }}{{ record.message_body?.length > 60 ? '...' : '' }}</span></a-tooltip>
          </template>
          <template v-if="column.key === 'error'">
            <a-tooltip v-if="record.error_message" :title="record.error_message"><span style="color: red">{{ record.error_message.substring(0, 40) }}...</span></a-tooltip>
            <span v-else>-</span>
          </template>
        </template>
      </a-table>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import api from '../api'

// 配置
const config = reactive({ dingtalk_webhook_url: '', dingtalk_webhook_secret: '', enabled: true })
const savingConfig = ref(false)
const testingSend = ref(false)

// 日志
const logs = ref<any[]>([])
const logsLoading = ref(false)
const eventTypeFilter = ref<string | undefined>()
const logsPag = reactive({ current: 1, pageSize: 20, total: 0 })

const eventTypeLabels: Record<string, string> = {
  generation_done: '生成完成', generation_failed: '生成失败',
  execution_done: '执行完成', execution_failed: '执行失败',
  upload_done: '上传成功',
}
const eventTypeColors: Record<string, string> = {
  generation_done: 'green', generation_failed: 'red',
  execution_done: 'blue', execution_failed: 'orange',
  upload_done: 'cyan',
}

const logColumns = [
  { title: 'ID', dataIndex: 'id', width: 60 },
  { title: '事件类型', key: 'event_type', width: 120 },
  { title: '渠道', dataIndex: 'channel', width: 80 },
  { title: '标题', dataIndex: 'message_title', ellipsis: true },
  { title: '内容', key: 'message_body', width: 200 },
  { title: '状态', key: 'log_status', width: 80 },
  { title: '错误', key: 'error', width: 150 },
  { title: '时间', dataIndex: 'created_at', width: 170 },
]

const loadConfig = async () => {
  try {
    const res: any = await api.get('/notifications/config')
    Object.assign(config, res.data)
  } catch { /* ignore */ }
}

const saveConfig = async () => {
  savingConfig.value = true
  try {
    await api.put('/notifications/config', config)
    message.success('配置已保存')
  } catch (e: any) {
    const detail = e.response?.data?.detail || e.message || '未知错误'
    message.error(`保存失败: ${detail}`)
  }
  savingConfig.value = false
}

const testSend = async () => {
  if (!config.dingtalk_webhook_url) {
    message.warning('请先填写 Webhook URL 并保存')
    return
  }
  testingSend.value = true
  try {
    await api.post('/notifications/test-send')
    message.success('测试通知发送成功，请在钉钉群查看')
    loadLogs()
  } catch (e: any) {
    const detail = e.response?.data?.detail || e.message || '未知错误'
    message.error(`测试发送失败: ${detail}`)
  }
  testingSend.value = false
}

const loadLogs = async () => {
  logsLoading.value = true
  const params: any = { page: logsPag.current, page_size: logsPag.pageSize }
  if (eventTypeFilter.value) params.event_type = eventTypeFilter.value
  try {
    const res: any = await api.get('/notifications/logs', { params })
    logs.value = res.data.items
    logsPag.total = res.data.total
  } catch { /* ignore */ }
  logsLoading.value = false
}

const onLogsChange = (pag: any) => {
  logsPag.current = pag.current
  loadLogs()
}

onMounted(() => {
  loadConfig()
  loadLogs()
})
</script>
