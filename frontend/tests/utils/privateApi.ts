// Note: the `PrivateService` is only available when generating the client
// for local environments
import axios from "axios"

const api = axios.create({ baseURL: process.env.NEXT_PUBLIC_API_URL })

export const createUser = async ({
  email,
  password,
}: {
  email: string
  password: string
}) => {
  return await api.post("/api/v1/private/users/", {
    email,
    password,
    is_verified: true,
    full_name: "Test User",
  })
}
