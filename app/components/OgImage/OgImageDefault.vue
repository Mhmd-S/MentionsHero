<script setup lang="ts">
defineOgImageComponent()
</script>

<template>
  <div
    class="flex h-full w-full flex-col items-center justify-center"
    :style="{
      background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)',
      fontFamily: 'sans-serif',
      padding: '60px',
    }"
  >
    <div
      :style="{
        fontSize: '28px',
        color: '#38bdf8',
        marginBottom: '16px',
        letterSpacing: '0.05em',
      }"
    >
      MentionsHero
    </div>
    <div
      :style="{
        fontSize: '48px',
        fontWeight: 'bold',
        color: '#f1f5f9',
        textAlign: 'center',
        lineHeight: '1.2',
        marginBottom: '24px',
      }"
    >
      Video Transcripts & Mentions Analysis
    </div>
    <div
      :style="{
        fontSize: '22px',
        color: '#94a3b8',
        textAlign: 'center',
        maxWidth: '800px',
      }"
    >
      Search press briefing transcripts. Track what public figures say linked to prediction markets.
    </div>
  </div>
</template>
