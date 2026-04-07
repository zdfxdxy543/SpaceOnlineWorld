<script setup>
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { getBoards, getHotThreads } from '../api/forumApi'

const loading = ref(true)
const boards = ref([])
const hotThreads = ref([])
const error = ref('')

function stageClass(stage) {
  return `stage-${String(stage || 'discussion').toLowerCase()}`
}

function stageLabel(stage) {
  const normalized = String(stage || 'discussion').toLowerCase()
  return normalized.charAt(0).toUpperCase() + normalized.slice(1)
}

async function loadBoards() {
  loading.value = true
  error.value = ''
  try {
    const [boardData, threadData] = await Promise.all([getBoards(), getHotThreads(8)])
    boards.value = boardData || []
    hotThreads.value = threadData || []
  } catch (err) {
    error.value = String(err)
  } finally {
    loading.value = false
  }
}

onMounted(loadBoards)
</script>

<template>
  <section class="grid-2">
    <div class="card">
      <h2>Forum Home</h2>
      <p class="muted">Boards, investigations, and user profiles are split into dedicated read-only pages.</p>

      <div v-if="loading" class="muted">Loading boards...</div>
      <div v-else>
        <div v-for="board in boards" :key="board.slug" class="card">
          <RouterLink :to="`/forum/board/${board.slug}`">{{ board.name }}</RouterLink>
          <p class="muted">{{ board.description }}</p>
          <p class="muted">Moderator: {{ board.moderator }} | Threads {{ board.threads }} | Posts {{ board.posts }}</p>
          <div v-if="board.latest_thread" class="muted">
            Latest: <RouterLink :to="`/forum/thread/${board.latest_thread.id}`">{{ board.latest_thread.title }}</RouterLink>
          </div>
        </div>
      </div>
      <p v-if="error" class="muted">{{ error }}</p>
    </div>

    <div class="card">
      <h2>Hot Threads</h2>
      <div v-if="loading" class="muted">Loading hot threads...</div>
      <ul v-else>
        <li v-for="thread in hotThreads" :key="thread.id" class="card">
          <RouterLink :to="`/forum/thread/${thread.id}`">{{ thread.title }}</RouterLink>
          <div class="muted">Board {{ thread.board_slug }} | By {{ thread.author_id }} | Replies {{ thread.replies }}</div>
          <div class="stage-chip" :class="stageClass(thread.stage)">
            Stage: {{ stageLabel(thread.stage) }}
          </div>
        </li>
      </ul>
      <h2>AI-Controlled Forum</h2>
      <p class="muted">
        Thread creation and replies are executed by backend AI actors only.
      </p>
      <p class="muted">
        This interface is a read-only observation console for event progression and stage tracking.
      </p>
    </div>
  </section>
</template>