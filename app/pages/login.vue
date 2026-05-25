<script setup lang="ts">
import * as z from 'zod'
import type { FormSubmitEvent, AuthFormField } from '@nuxt/ui'

definePageMeta({ layout: false });

const route = useRoute();
const { login, error: authError, loading } = useAuth();

const externalError = ref<string | null>(
  route.query.error ? (route.query.error as string).replace(/\+/g, ' ') : null
);
const error = computed(() => externalError.value || authError.value);

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
  placeholder: 'Enter your password',
  required: true
}]

const schema = z.object({
  email: z.email('Invalid email'),
  password: z.string('Password is required').min(1, 'Password is required')
})

type Schema = z.output<typeof schema>

async function onSubmit(payload: FormSubmitEvent<Schema>) {
  externalError.value = null;
  const success = await login(payload.data.email, payload.data.password);
  if (success) {
    navigateTo('/admin');
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-muted p-4">
    <UPageCard class="w-full max-w-md">
      <UAuthForm
        :schema="schema"
        :fields="fields"
        :loading="loading"
        title="MentionsHero"
        description="Sign in to continue"
        icon="i-lucide-message-circle"
        @submit="onSubmit"
      >
        <template v-if="error" #validation>
          <UAlert color="error" icon="i-lucide-info" :title="error" />
        </template>
      </UAuthForm>
    </UPageCard>
  </div>
</template>
