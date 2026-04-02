import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    component: () => import('../layouts/MainLayout.vue'),
    children: [
      { path: '', name: 'Dashboard', component: () => import('../views/Dashboard.vue') },
      { path: 'requirements', name: 'Requirements', component: () => import('../views/Requirements.vue') },
      { path: 'specs', name: 'Specs', component: () => import('../views/TestCaseSpecs.vue') },
      { path: 'testcases', name: 'TestCases', component: () => import('../views/TestCases.vue') },
      { path: 'generation', name: 'Generation', component: () => import('../views/GenerationJobs.vue') },
      { path: 'execution', name: 'Execution', component: () => import('../views/ExecutionJobs.vue') },
      { path: 'notifications', name: 'Notifications', component: () => import('../views/Notifications.vue') },
    ],
  },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
