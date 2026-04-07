<script setup>
import { onMounted, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { getCategory } from '../api/newsApi'

const route = useRoute()
const loading = ref(true)
const category = ref(null)
const articles = ref([])
const error = ref('')

function stageClass(stage) {
  return `stage-${String(stage || 'breaking').toLowerCase()}`
}

function stageLabel(stage) {
  const normalized = String(stage || 'breaking').toLowerCase()
  return normalized.charAt(0).toUpperCase() + normalized.slice(1)
}

async function loadCategory() {
  loading.value = true
  error.value = ''
  try {
    const data = await getCategory(route.params.categorySlug)
    category.value = data.category || null
    articles.value = data.articles || []
  } catch (err) {
    error.value = String(err)
  } finally {
    loading.value = false
  }
}

onMounted(loadCategory)
</script>

<template>
  <section class="card">
    <p class="muted"><RouterLink to="/news">Back to News Home</RouterLink></p>
    <div v-if="loading" class="muted">Loading category...</div>
    <div v-else-if="category">
      <h2>{{ category.name }}</h2>
      <p class="muted">{{ category.description }}</p>
      <p class="muted">Articles {{ category.article_count }}</p>

      <ul>
        <li v-for="article in articles" :key="article.article_id" class="card">
          <RouterLink :to="`/news/article/${article.article_id}`">{{ article.title }}</RouterLink>
          <div class="muted">By {{ article.author_id }} | Views {{ article.views }}</div>
          <div class="stage-chip" :class="stageClass(article.stage)">
            Stage: {{ stageLabel(article.stage) }}
          </div>
          <p>{{ article.excerpt }}</p>
        </li>
      </ul>
    </div>
    <p v-else class="muted">Category not found.</p>
    <p v-if="error" class="muted">{{ error }}</p>
  </section>
</template>
