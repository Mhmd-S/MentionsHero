<script setup lang="ts">
definePageMeta({ layout: false })

useSeoMeta({
  title: 'Sign Up',
  description: 'Create a free MentionsHero account to access press briefing transcripts and mentions analysis.',
  robots: 'noindex, nofollow',
})

const firstName = ref('')
const lastName = ref('')
const phone = ref('')
const email = ref('')
const password = ref('')
const error = ref<string | null>(null)
const loading = ref(false)
const emailSent = ref(false)

async function handleSignup() {
  error.value = null
  loading.value = true

  try {
    const supabase = useSupabaseClient()

    const { data, error: signupError } = await supabase.auth.signUp({
      email: email.value,
      password: password.value,
      options: {
        data: {
          first_name: firstName.value,
          last_name: lastName.value,
          phone: phone.value,
        },
      },
    })

    if (signupError) {
      error.value = signupError.message
      return
    }

    if (data.user) {
      // Create profile via backend API (service key bypasses RLS)
      await $fetch('/api/profile/init', {
        method: 'POST',
        body: {
          user_id: data.user.id,
          first_name: firstName.value,
          last_name: lastName.value,
          phone: phone.value,
        },
      })

      // Show email verification message instead of auto-login
      emailSent.value = true
    }
  } catch (err: any) {
    error.value = err.message || 'Signup failed'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-muted p-4">
    <UCard class="w-full max-w-md">
      <template #header>
        <div class="text-center">
          <UIcon name="i-lucide-message-circle" class="size-8 text-primary mx-auto mb-2" />
          <h1 class="text-xl font-bold">Create Account</h1>
          <p class="text-sm text-muted mt-1">Sign up for MentionsHero</p>
        </div>
      </template>

      <!-- Email verification success -->
      <div v-if="emailSent" class="space-y-4 text-center">
        <UIcon name="i-lucide-mail" class="size-12 text-primary mx-auto" />
        <h2 class="text-lg font-semibold">Check your email</h2>
        <p class="text-sm text-muted">
          We sent a verification link to <strong>{{ email }}</strong>. Please click the link to verify your account.
        </p>
        <UButton variant="outline" block @click="navigateTo('/login')">
          Go to Sign In
        </UButton>
      </div>

      <!-- Signup form -->
      <form v-else class="space-y-4" @submit.prevent="handleSignup">
        <UAlert v-if="error" color="error" :title="error" />

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <UFormField label="First Name">
            <UInput
              v-model="firstName"
              placeholder="John"
              required
              class="w-full"
            />
          </UFormField>

          <UFormField label="Last Name">
            <UInput
              v-model="lastName"
              placeholder="Doe"
              required
              class="w-full"
            />
          </UFormField>
        </div>

        <UFormField label="Phone Number">
          <UInput
            v-model="phone"
            type="tel"
            placeholder="+1 (555) 000-0000"
            required
            class="w-full"
          />
        </UFormField>

        <UFormField label="Email">
          <UInput
            v-model="email"
            type="email"
            placeholder="you@example.com"
            required
            class="w-full"
          />
        </UFormField>

        <UFormField label="Password">
          <UInput
            v-model="password"
            type="password"
            placeholder="At least 6 characters"
            required
            class="w-full"
          />
        </UFormField>

        <UButton type="submit" block :loading="loading">
          Sign Up
        </UButton>
      </form>

      <template #footer>
        <p v-if="!emailSent" class="text-sm text-center text-muted">
          Already have an account?
          <NuxtLink to="/login" class="text-primary hover:underline">Sign in</NuxtLink>
        </p>
      </template>
    </UCard>
  </div>
</template>
