<template>
  <a-layout style="min-height: 100vh">
    <a-layout-sider v-model:collapsed="collapsed" collapsible theme="dark">
      <div class="logo">
        <h2 v-if="!collapsed">QA Master</h2>
        <h2 v-else>QA</h2>
      </div>
      <a-menu theme="dark" mode="inline" :selectedKeys="selectedKeys" @click="onMenuClick">
        <a-menu-item key="Dashboard">
          <DashboardOutlined /><span>仪表盘</span>
        </a-menu-item>
        <a-menu-item key="Requirements">
          <FileTextOutlined /><span>需求管理</span>
        </a-menu-item>
        <a-menu-item key="Specs">
          <ProfileOutlined /><span>用例规范</span>
        </a-menu-item>
        <a-menu-item key="TestCases">
          <UnorderedListOutlined /><span>用例管理</span>
        </a-menu-item>
        <a-menu-item key="Generation">
          <ThunderboltOutlined /><span>用例生成</span>
        </a-menu-item>
        <a-menu-item key="Execution">
          <PlayCircleOutlined /><span>用例执行</span>
        </a-menu-item>
        <a-menu-item key="Notifications">
          <BellOutlined /><span>通知管理</span>
        </a-menu-item>
      </a-menu>
    </a-layout-sider>
    <a-layout>
      <a-layout-header style="background: #fff; padding: 0 24px; display: flex; align-items: center;">
        <h3 style="margin: 0;">{{ currentTitle }}</h3>
      </a-layout-header>
      <a-layout-content style="margin: 16px; padding: 24px; background: #fff; border-radius: 8px; min-height: 360px;">
        <router-view />
      </a-layout-content>
    </a-layout>
  </a-layout>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  DashboardOutlined, FileTextOutlined, ProfileOutlined,
  UnorderedListOutlined, ThunderboltOutlined, PlayCircleOutlined, BellOutlined,
} from '@ant-design/icons-vue'

const router = useRouter()
const route = useRoute()
const collapsed = ref(false)

const titleMap: Record<string, string> = {
  Dashboard: '仪表盘',
  Requirements: '需求管理',
  Specs: '用例规范',
  TestCases: '用例管理',
  Generation: '用例生成',
  Execution: '用例执行',
  Notifications: '通知管理',
}

const selectedKeys = computed(() => [route.name as string])
const currentTitle = computed(() => titleMap[route.name as string] || 'QA Master')

const onMenuClick = ({ key }: { key: string }) => {
  router.push({ name: key })
}
</script>

<style scoped>
.logo {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
}
.logo h2 {
  margin: 0;
  color: #fff;
  font-size: 18px;
}
</style>
