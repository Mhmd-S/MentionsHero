import { getActiveJobs } from '../../utils/job-progress'

export default defineEventHandler(async () => {
  const jobs = await getActiveJobs()
  return { jobs }
})
