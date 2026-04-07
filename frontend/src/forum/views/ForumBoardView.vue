<script setup>
import { onMounted, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { getBoardThreads } from '../api/forumApi'

const route = useRoute()
const loading = ref(true)
const board = ref(null)
const threads = ref([])
const error = ref('')

function stageClass(stage) {
  return `stage-${String(stage || 'discussion').toLowerCase()}`
}

function stageLabel(stage) {
  const normalized = String(stage || 'discussion').toLowerCase()
  return normalized.charAt(0).toUpperCase() + normalized.slice(1)
}

async function loadBoard() {
  loading.value = true
  error.value = ''
  try {
    const data = await getBoardThreads(route.params.boardSlug)
    board.value = data.board || null
    threads.value = data.threads || []
  } catch (err) {
    error.value = String(err)
  } finally {
    loading.value = false
  }
}

onMounted(loadBoard)
</script>

<template>
  <section class="card">
    <p class="muted"><RouterLink to="/forum">Back to Forum Home</RouterLink></p>
    <div v-if="loading" class="muted">Loading board...</div>
    <div v-else-if="board">
      <h2>{{ board.name }}</h2>
      <p class="muted">{{ board.description }}</p>
      <p class="muted">Moderator: {{ board.moderator }} | Threads {{ board.threads }} | Posts {{ board.posts }}</p>

      <ul>
        <li v-for="thread in threads" :key="thread.id" class="card">
          <RouterLink :to="`/forum/thread/${thread.id}`">{{ thread.title }}</RouterLink>
          <div class="muted">
            By <RouterLink :to="`/forum/user/${thread.author_id}`">{{ thread.author_id }}</RouterLink>
            | Replies {{ thread.replies }} | Views {{ thread.views }}
          </div>
          <div class="stage-chip" :class="stageClass(thread.stage)">
            Stage: {{ stageLabel(thread.stage) }}
          </div>
        </li>
      </ul>
    </div>
    <p v-else class="muted">Board not found.</p>
    <p v-if="error" class="muted">{{ error }}</p>
  </section>
</template>
