import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/news' },
  {
    path: '/news',
    name: 'news',
    component: () => import('../news/views/NewsView.vue'),
  },
  {
    path: '/news/category/:categorySlug',
    name: 'news-category',
    component: () => import('../news/views/NewsCategoryView.vue'),
  },
  {
    path: '/news/article/:articleId',
    name: 'news-article',
    component: () => import('../news/views/NewsArticleView.vue'),
  },
  {
    path: '/forum',
    name: 'forum',
    component: () => import('../forum/views/ForumView.vue'),
  },
  {
    path: '/forum/board/:boardSlug',
    name: 'forum-board',
    component: () => import('../forum/views/ForumBoardView.vue'),
  },
  {
    path: '/forum/thread/:threadId',
    name: 'forum-thread',
    component: () => import('../forum/views/ForumThreadView.vue'),
  },
  {
    path: '/forum/user/:userId',
    name: 'forum-user',
    component: () => import('../forum/views/ForumUserView.vue'),
  },
]

export default createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})