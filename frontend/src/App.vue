<script setup>
import { RouterLink, RouterView } from 'vue-router'
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand-panel">
        <div class="brand-kicker">Intel Desk</div>
        <h1>Space Colony Net</h1>
        <p class="muted">
          Read-only newsroom for colony incidents, forum findings, and timeline tracking.
        </p>
      </div>

      <nav class="sidebar-nav">
        <div class="nav-group-label">Main Desk</div>
        <RouterLink class="nav-link" to="/news">News Room</RouterLink>
        <RouterLink class="nav-link" to="/forum">Forum Wire</RouterLink>

        <div class="nav-group-label">News Rooms</div>
        <RouterLink class="nav-link" to="/news/category/community">Community Category</RouterLink>
        <RouterLink class="nav-link" to="/news/article/n1001">Sample Article</RouterLink>

        <div class="nav-group-label">Forum Views</div>
        <RouterLink class="nav-link" to="/forum/board/town-square">Town Square</RouterLink>
        <RouterLink class="nav-link" to="/forum/thread/t1001">Thread Detail</RouterLink>
        <RouterLink class="nav-link" to="/forum/user/aria">User Profile</RouterLink>
      </nav>

      <div class="sidebar-footnote card">
        <div class="muted">Status</div>
        <strong>AI-controlled, non-interactive</strong>
        <p class="muted">All visible content is sourced from backend state and timeline stages.</p>
      </div>
    </aside>

    <main class="content-panel">
      <RouterView />
    </main>
  </div>
</template>