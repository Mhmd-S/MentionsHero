/**
 * Composable for persona management API interactions
 */

export interface Persona {
  id: string;
  name: string;
  slug: string | null;
  description: string | null;
  meta_title: string | null;
  meta_description: string | null;
  aliases: string[];
  created_at: string | null;
  updated_at: string | null;
}

export interface PersonaTranscript {
  id: string;
  name: string;
  youtube_url: string;
  created_at: string;
  folder_id: string | null;
}

export function usePersonas() {
  const { authFetch } = useAuthFetch();
  const personas = useState<Persona[]>('personas-list', () => []);
  const loading = useState<boolean>('personas-loading', () => false);
  const error = useState<string | null>('personas-error', () => null);

  /**
   * Fetch all personas
   */
  async function fetchPersonas(): Promise<Persona[]> {
    loading.value = true;
    error.value = null;
    try {
      const result = await authFetch<Persona[]>('/api/personas');
      personas.value = Array.isArray(result) ? result : [];
      return personas.value;
    } catch (e: any) {
      error.value = e.message || 'Failed to fetch personas';
      console.error('Failed to fetch personas:', e);
      return [];
    } finally {
      loading.value = false;
    }
  }

  /**
   * Get a single persona by ID
   */
  async function getPersona(id: string): Promise<Persona | null> {
    try {
      const result = await authFetch<Persona>(`/api/personas/${id}`);
      return result;
    } catch (e: any) {
      console.error('Failed to fetch persona:', e);
      return null;
    }
  }

  /**
   * Create a new persona
   */
  async function createPersona(
    name: string,
    description?: string,
    aliases?: string[],
    meta_title?: string,
    meta_description?: string,
  ): Promise<Persona | null> {
    loading.value = true;
    error.value = null;
    try {
      const result = await authFetch<Persona>('/api/personas', {
        method: 'POST',
        body: { name, description, meta_title, meta_description, aliases: aliases || [] }
      });
      // Refresh list
      await fetchPersonas();
      return result;
    } catch (e: any) {
      error.value = e.message || 'Failed to create persona';
      console.error('Failed to create persona:', e);
      return null;
    } finally {
      loading.value = false;
    }
  }

  /**
   * Update a persona
   */
  async function updatePersona(
    id: string,
    name?: string,
    description?: string,
    meta_title?: string,
    meta_description?: string,
    slug?: string,
  ): Promise<Persona | null> {
    loading.value = true;
    error.value = null;
    try {
      const result = await authFetch<Persona>(`/api/personas/${id}`, {
        method: 'PATCH',
        body: { name, description, meta_title, meta_description, slug }
      });
      // Refresh list
      await fetchPersonas();
      return result;
    } catch (e: any) {
      error.value = e.message || 'Failed to update persona';
      console.error('Failed to update persona:', e);
      return null;
    } finally {
      loading.value = false;
    }
  }

  /**
   * Delete a persona
   */
  async function deletePersona(id: string): Promise<boolean> {
    loading.value = true;
    error.value = null;
    try {
      await authFetch(`/api/personas/${id}`, { method: 'DELETE' });
      // Refresh list
      await fetchPersonas();
      return true;
    } catch (e: any) {
      error.value = e.message || 'Failed to delete persona';
      console.error('Failed to delete persona:', e);
      return false;
    } finally {
      loading.value = false;
    }
  }

  /**
   * Add aliases to a persona
   */
  async function addAliases(id: string, aliases: string[]): Promise<Persona | null> {
    loading.value = true;
    error.value = null;
    try {
      const result = await authFetch<Persona>(`/api/personas/${id}/aliases`, {
        method: 'POST',
        body: { aliases }
      });
      // Refresh list
      await fetchPersonas();
      return result;
    } catch (e: any) {
      error.value = e.message || 'Failed to add aliases';
      console.error('Failed to add aliases:', e);
      return null;
    } finally {
      loading.value = false;
    }
  }

  /**
   * Remove aliases from a persona
   */
  async function removeAliases(id: string, aliases: string[]): Promise<Persona | null> {
    loading.value = true;
    error.value = null;
    try {
      const result = await authFetch<Persona>(`/api/personas/${id}/aliases`, {
        method: 'DELETE',
        body: { aliases }
      });
      // Refresh list
      await fetchPersonas();
      return result;
    } catch (e: any) {
      error.value = e.message || 'Failed to remove aliases';
      console.error('Failed to remove aliases:', e);
      return null;
    } finally {
      loading.value = false;
    }
  }

  /**
   * Get transcripts for a persona
   */
  async function getPersonaTranscripts(
    id: string,
    folderId?: string | null
  ): Promise<PersonaTranscript[]> {
    try {
      const result = await authFetch<PersonaTranscript[]>(
        `/api/personas/${id}/transcripts`,
        { query: folderId ? { folder_id: folderId } : undefined }
      );
      return result || [];
    } catch (e: any) {
      console.error('Failed to fetch persona transcripts:', e);
      return [];
    }
  }

  /**
   * Helper to get aliases for a specific persona
   */
  function getAliasesForPersona(id: string): string[] {
    const persona = personas.value.find(p => p.id === id);
    return persona?.aliases || [];
  }

  /**
   * Helper to find persona by alias
   */
  function findPersonaByAlias(alias: string): Persona | undefined {
    return personas.value.find(p =>
      p.aliases.some(a => a.toLowerCase() === alias.toLowerCase())
    );
  }

  return {
    personas: readonly(personas),
    loading: readonly(loading),
    error: readonly(error),
    fetchPersonas,
    getPersona,
    createPersona,
    updatePersona,
    deletePersona,
    addAliases,
    removeAliases,
    getPersonaTranscripts,
    getAliasesForPersona,
    findPersonaByAlias,
  };
}
