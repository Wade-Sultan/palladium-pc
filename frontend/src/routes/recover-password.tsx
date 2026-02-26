import { zodResolver } from "@hookform/resolvers/zod"
import {
  createFileRoute,
  Link as RouterLink,
  redirect,
} from "@tanstack/react-router"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { AuthLayout } from "@/components/Common/AuthLayout"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import { isLoggedIn } from "@/hooks/useAuth"
import useAuth from "@/hooks/useAuth"

const formSchema = z.object({
  email: z.string().email({ message: "Please enter a valid email" }),
})

type FormData = z.infer<typeof formSchema>

export const Route = createFileRoute("/recover-password")({
  component: RecoverPassword,
  beforeLoad: async () => {
    if (await isLoggedIn()) {
      throw redirect({ to: "/" })
    }
  },
  head: () => ({
    meta: [{ title: "Recover Password - Palladium" }],
  }),
})

function RecoverPassword() {
  const { resetPassword } = useAuth()
  const [submitting, setSubmitting] = useState(false)
  const [sent, setSent] = useState(false)

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      email: "",
    },
  })

  const onSubmit = async (data: FormData) => {
    if (submitting) return
    setSubmitting(true)
    const { error } = await resetPassword(data.email)
    if (error) {
      form.setError("root", { message: error.message })
    } else {
      setSent(true)
    }
    setSubmitting(false)
  }

  return (
    <AuthLayout>
      <Form {...form}>
        <form
          onSubmit={form.handleSubmit(onSubmit)}
          className="flex flex-col gap-6"
        >
          <div className="flex flex-col items-center gap-2 text-center">
            <h1 className="text-2xl font-bold">Recover Password</h1>
            <p className="text-sm text-muted-foreground">
              Enter your email and we'll send you a link to reset your password.
            </p>
          </div>

          {form.formState.errors.root && (
            <p className="text-sm text-destructive text-center">
              {form.formState.errors.root.message}
            </p>
          )}

          {sent ? (
            <div className="text-center">
              <p className="text-sm text-muted-foreground">
                If an account exists for that email, you'll receive a password
                reset link shortly. Check your inbox.
              </p>
            </div>
          ) : (
            <div className="grid gap-4">
              <FormField
                control={form.control}
                name="email"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Email</FormLabel>
                    <FormControl>
                      <Input
                        placeholder="you@example.com"
                        type="email"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <LoadingButton type="submit" loading={submitting}>
                Send Reset Link
              </LoadingButton>
            </div>
          )}

          <div className="text-center text-sm">
            <RouterLink to="/login" className="underline underline-offset-4">
              Back to login
            </RouterLink>
          </div>
        </form>
      </Form>
    </AuthLayout>
  )
}
