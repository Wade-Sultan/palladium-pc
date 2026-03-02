import { zodResolver } from "@hookform/resolvers/zod"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { LoadingButton } from "@/components/ui/loading-button"
import { PasswordInput } from "@/components/ui/password-input"
import useAuth from "@/hooks/useAuth"

const formSchema = z
  .object({
    new_password: z
      .string()
      .min(1, { message: "Password is required" })
      .min(8, { message: "Password must be at least 8 characters" }),
    confirm_password: z
      .string()
      .min(1, { message: "Password confirmation is required" }),
  })
  .refine((data) => data.new_password === data.confirm_password, {
    message: "The passwords don't match",
    path: ["confirm_password"],
  })

type FormData = z.infer<typeof formSchema>

const ChangePassword = () => {
  const { updatePassword } = useAuth()
  const [submitting, setSubmitting] = useState(false)

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    mode: "onSubmit",
    criteriaMode: "all",
    defaultValues: {
      new_password: "",
      confirm_password: "",
    },
  })

  const onSubmit = async (data: FormData) => {
    if (submitting) return
    setSubmitting(true)
    const { error } = await updatePassword(data.new_password)
    if (error) {
      form.setError("root", { message: error.message })
    } else {
      form.reset()
    }
    setSubmitting(false)
  }

  return (
    <div className="max-w-md">
      <h3 className="text-lg font-semibold py-4">Change Password</h3>
      <Form {...form}>
        <form
          onSubmit={form.handleSubmit(onSubmit)}
          className="flex flex-col gap-4"
        >
          {form.formState.errors.root && (
            <p className="text-sm text-destructive">
              {form.formState.errors.root.message}
            </p>
          )}

          <FormField
            control={form.control}
            name="new_password"
            render={({ field, fieldState }) => (
              <FormItem>
                <FormLabel>New Password</FormLabel>
                <FormControl>
                  <PasswordInput
                    data-testid="new-password-input"
                    placeholder="••••••••"
                    aria-invalid={fieldState.invalid}
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="confirm_password"
            render={({ field, fieldState }) => (
              <FormItem>
                <FormLabel>Confirm Password</FormLabel>
                <FormControl>
                  <PasswordInput
                    data-testid="confirm-password-input"
                    placeholder="••••••••"
                    aria-invalid={fieldState.invalid}
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <LoadingButton
            type="submit"
            loading={submitting}
            className="self-start"
          >
            Update Password
          </LoadingButton>
        </form>
      </Form>
    </div>
  )
}

export default ChangePassword
