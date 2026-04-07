<script setup>
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { getHotArticles, listCategories } from '../api/newsApi'

const loading = ref(true)
const categories = ref([])
const hotArticles = ref([])
const error = ref('')

function stageClass(stage) {
  return `stage-${String(stage || 'breaking').toLowerCase()}`
}

function stageLabel(stage) {
  const normalized = String(stage || 'breaking').toLowerCase()
  return normalized.charAt(0).toUpperCase() + normalized.slice(1)
}

async function loadInitial() {
  loading.value = true
  error.value = ''
  try {
    const [categoryData, articleData] = await Promise.all([listCategories(), getHotArticles(8)])
    categories.value = categoryData.categories || []
    hotArticles.value = articleData.articles || []
  } catch (err) {
    error.value = String(err)
  } finally {
    loading.value = false
  }
}

onMounted(loadInitial)
</script>

<template>
  <section class="grid-2">
    <div class="card">
      <h2>News Home</h2>
      <p class="muted">Official updates, investigation reports, and colony announcements.</p>

      <div v-if="loading" class="muted">Loading news...</div>
      <div v-else>
        <h3>Categories</h3>
        <div class="grid-2">
          <div v-for="category in categories" :key="category.slug" class="card">
            <RouterLink :to="`/news/category/${category.slug}`">{{ category.name }}</RouterLink>
            <p class="muted">{{ category.description }}</p>
            <div class="muted">{{ category.article_count }} articles</div>
          </div>
        </div>
      </div>
      <p v-if="error" class="muted">{{ error }}</p>
    </div>

    <div class="card">
      <h2>Hot Articles</h2>
      <div v-if="loading" class="muted">Loading hot articles...</div>
      <ul v-else>
        <li v-for="article in hotArticles" :key="article.article_id" class="card">
          <RouterLink :to="`/news/article/${article.article_id}`">{{ article.title }}</RouterLink>
          <div class="muted">
            Category <RouterLink :to="`/news/category/${article.category}`">{{ article.category }}</RouterLink>
            | By {{ article.author_id }} | Views {{ article.views }}
          </div>
          <div class="stage-chip" :class="stageClass(article.stage)">
            Stage: {{ stageLabel(article.stage) }}
          </div>
          <p>{{ article.excerpt }}</p>
        </li>
      </ul>
      <h2>AI-Controlled Feed</h2>
      <p class="muted">
        Frontend interaction is intentionally disabled. News publishing is executed by backend AI workflows and
        scheduler pipelines.
      </p>
      <p class="muted">
        This panel is read-only by design and only visualizes timeline stage progression.
      </p>
    </div>
  </section>
</template>