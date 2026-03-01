<script setup lang="ts">
import * as z from 'zod'
import type { FormSubmitEvent, AuthFormField } from '@nuxt/ui'

definePageMeta({ layout: false });

const { login, error, loading } = useAuth();

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
  const success = await login(payload.data.email, payload.data.password);
  if (success) {
    // Check role and redirect accordingly
    const supabase = useSupabaseClient();
    const { data: { session } } = await supabase.auth.getSession();
    if (session) {
      const { data: profile } = await supabase
        .from('profiles')
        .select('role')
        .eq('id', session.user.id)
        .single();

      if (profile?.role === 'admin') {
        navigateTo('/admin');
      } else {
        navigateTo('/');
      }
    } else {
      navigateTo('/');
    }
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
        icon="i-ph-chat-circle-dots-fill"
        @submit="onSubmit"
      >
        <template v-if="error" #validation>
          <UAlert color="error" icon="i-ph-info" :title="error" />
        </template>
      </UAuthForm>
      <div class="text-center mt-4">
        <p class="text-sm text-muted">
          Don't have an account?
          <NuxtLink to="/signup" class="text-primary hover:underline">Sign up</NuxtLink>
        </p>
      </div>
    </UPageCard>
  </div>
</template>
