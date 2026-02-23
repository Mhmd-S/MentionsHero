<script setup lang="ts">
import * as z from 'zod'
import type { FormSubmitEvent, AuthFormField } from '@nuxt/ui'

definePageMeta({ layout: false });

useHead({ title: 'Sign Up' })
useServerSeoMeta({ robots: 'noindex, nofollow' })

const { signup, error, loading } = useAuth();
const signedUp = ref(false);

const fields: AuthFormField[] = [{
  name: 'email',
  type: 'email',
  label: 'Email',
  placeholder: 'Enter your email',
  required: true
}, {
  name: 'password',
  label: 'Password',
  type: 'password',
  placeholder: 'Create a password',
  required: true
}]

const schema = z.object({
  email: z.email('Invalid email'),
  password: z.string('Password is required').min(6, 'Password must be at least 6 characters')
})

type Schema = z.output<typeof schema>

async function onSubmit(payload: FormSubmitEvent<Schema>) {
  const success = await signup(payload.data.email, payload.data.password);
  if (success) {
    const { session } = useAuth();
    if (session.value) {
      navigateTo('/');
    } else {
      // Email confirmation required
      signedUp.value = true;
    }
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950">
    <UPageCard class="w-full max-w-md">
      <template v-if="signedUp">
        <div class="text-center py-6">
          <UIcon name="i-heroicons-envelope" class="size-12 text-primary mx-auto mb-4" />
          <h2 class="text-xl font-semibold mb-2">Check your email</h2>
          <p class="text-gray-500 text-sm">We sent you a confirmation link. Click it to activate your account.</p>
          <NuxtLink to="/login" class="text-primary text-sm mt-4 inline-block hover:underline">
            Back to sign in
          </NuxtLink>
        </div>
      </template>

      <template v-else>
        <UAuthForm
          :schema="schema"
          :fields="fields"
          :loading="loading"
          title="Transcripts"
          description="Create a free account"
          icon="i-heroicons-microphone"
          @submit="onSubmit"
        >
          <template v-if="error" #validation>
            <UAlert color="error" icon="i-heroicons-information-circle" :title="error" />
          </template>

          <template #footer>
            <p class="text-center text-sm text-gray-500">
              Already have an account?
              <NuxtLink to="/login" class="text-primary hover:underline">Sign in</NuxtLink>
            </p>
          </template>
        </UAuthForm>
      </template>
    </UPageCard>
  </div>
</template>
