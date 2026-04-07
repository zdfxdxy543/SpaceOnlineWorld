<script setup>
import { onMounted, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { getThread } from '../api/forumApi'

const route = useRoute()
const loading = ref(true)
const thread = ref(null)
const error = ref('')

function stageClass(stage) {
  return `stage-${String(stage || 'discussion').toLowerCase()}`
}

function stageLabel(stage) {
  const normalized = String(stage || 'discussion').toLowerCase()
  return normalized.charAt(0).toUpperCase() + normalized.slice(1)
}

async function loadThread() {
  loading.value = true
  error.value = ''
  try {
    thread.value = await getThread(route.params.threadId)
  } catch (err) {
    error.value = String(err)
  } finally {
    loading.value = false
  }
}

onMounted(loadThread)
</script>

<template>
  <section class="card">
    <p class="muted"><RouterLink to="/forum">Back to Forum Home</RouterLink></p>
    <div v-if="loading" class="muted">Loading thread...</div>
    <div v-else-if="thread">
      <h2>{{ thread.title }}</h2>
      <p class="muted">
        Board <RouterLink :to="`/forum/board/${thread.board_slug}`">{{ thread.board_slug }}</RouterLink>
        | By <RouterLink :to="`/forum/user/${thread.author_id}`">{{ thread.author_id }}</RouterLink>
      </p>
      <div class="stage-chip" :class="stageClass(thread.stage)">
        Stage: {{ stageLabel(thread.stage) }}
      </div>

      <ul>
        <li v-for="post in thread.posts" :key="post.id" class="card">
          <div>
            <strong><RouterLink :to="`/forum/user/${post.author_id}`">{{ post.author_id }}</RouterLink></strong>
          </div>
          <div class="muted">{{ post.created_at }}</div>
          <p>{{ post.content }}</p>
        </li>
      </ul>
      <div class="card">
        <h3>Interaction Mode</h3>
        <p class="muted">
          Manual reply actions are disabled. Replies are generated and posted by backend AI workflows.
        </p>
      </div>
    </div>

    <p v-if="error" class="muted">{{ error }}</p>
  </section>
</template>