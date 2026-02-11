<script setup lang="ts">
definePageMeta({ layout: false });

const { login, error, loading } = useAuth();

const email = ref("");
const password = ref("");

async function handleLogin() {
  const success = await login(email.value, password.value);
  if (success) {
    navigateTo("/");
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950">
    <div class="w-full max-w-sm space-y-6">
      <div class="text-center">
        <UIcon name="i-heroicons-microphone" class="size-10 text-primary mx-auto" />
        <h1 class="mt-4 text-2xl font-bold">Transcripts</h1>
        <p class="mt-1 text-sm text-gray-500">Sign in to continue</p>
      </div>

      <form class="space-y-4" @submit.prevent="handleLogin">
        <UInput
          v-model="email"
          type="email"
          placeholder="Email"
          size="lg"
          required
          autofocus
        />
        <UInput
          v-model="password"
          type="password"
          placeholder="Password"
          size="lg"
          required
        />

        <p v-if="error" class="text-sm text-red-500">{{ error }}</p>

        <UButton
          type="submit"
          block
          size="lg"
          :loading="loading"
        >
          Sign in
        </UButton>
      </form>
    </div>
  </div>
</template>
