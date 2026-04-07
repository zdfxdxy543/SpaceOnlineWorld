<script setup>
import { onMounted, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { getArticle } from '../api/newsApi'

const route = useRoute()
const loading = ref(true)
const article = ref(null)
const error = ref('')

function stageClass(stage) {
  return `stage-${String(stage || 'breaking').toLowerCase()}`
}

function stageLabel(stage) {
  const normalized = String(stage || 'breaking').toLowerCase()
  return normalized.charAt(0).toUpperCase() + normalized.slice(1)
}

async function loadArticle() {
  loading.value = true
  error.value = ''
  try {
    article.value = await getArticle(route.params.articleId)
  } catch (err) {
    error.value = String(err)
  } finally {
    loading.value = false
  }
}

onMounted(loadArticle)
</script>

<template>
  <section class="card">
    <p class="muted"><RouterLink to="/news">Back to News Home</RouterLink></p>
    <div v-if="loading" class="muted">Loading article...</div>
    <div v-else-if="article">
      <h2>{{ article.title }}</h2>
      <p class="muted">
        Category <RouterLink :to="`/news/category/${article.category}`">{{ article.category }}</RouterLink>
        | By {{ article.author_id }} | {{ article.published_at }} | Views {{ article.views }}
      </p>
      <div class="stage-chip" :class="stageClass(article.stage)">
        Stage: {{ stageLabel(article.stage) }}
      </div>
      <p>{{ article.content }}</p>

      <h3>Related Forum Threads</h3>
      <ul>
        <li v-for="threadId in article.related_thread_ids" :key="threadId">
          <RouterLink :to="`/forum/thread/${threadId}`">{{ threadId }}</RouterLink>
        </li>
      </ul>
    </div>
    <p v-if="error" class="muted">{{ error }}</p>
  </section>
</template>