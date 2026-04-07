<script setup>
import { onMounted, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { getUser } from '../api/forumApi'

const route = useRoute()
const loading = ref(true)
const user = ref(null)
const recentThreads = ref([])
const error = ref('')

async function loadUser() {
  loading.value = true
  error.value = ''
  try {
    const data = await getUser(route.params.userId)
    user.value = data.user || null
    recentThreads.value = data.recent_threads || []
  } catch (err) {
    error.value = String(err)
  } finally {
    loading.value = false
  }
}

onMounted(loadUser)
</script>

<template>
  <section class="card">
    <p class="muted"><RouterLink to="/forum">Back to Forum Home</RouterLink></p>
    <div v-if="loading" class="muted">Loading user...</div>
    <div v-else-if="user">
      <h2>{{ user.name }}</h2>
      <p class="muted">{{ user.title }} | {{ user.status }}</p>
      <p class="muted">Join date {{ user.join_date }} | Posts {{ user.posts }} | Reputation {{ user.reputation }}</p>
      <p>{{ user.bio }}</p>
      <p class="muted">Signature: {{ user.signature }}</p>

      <h3>Recent Threads</h3>
      <ul>
        <li v-for="thread in recentThreads" :key="thread.id" class="card">
          <RouterLink :to="`/forum/thread/${thread.id}`">{{ thread.title }}</RouterLink>
          <div class="muted">Board {{ thread.board_slug }} | Replies {{ thread.replies }}</div>
        </li>
      </ul>
    </div>
    <p v-else class="muted">User not found.</p>
    <p v-if="error" class="muted">{{ error }}</p>
  </section>
</template>
