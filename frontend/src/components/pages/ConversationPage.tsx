"use client"

import { useEffect, useState } from "react"
import Image from "next/image"
import { useRouter } from "next/navigation"
import { ArrowLeft, User } from "lucide-react"
import useAuth, { getAccessToken } from "@/hooks/useAuth"

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

interface Message {
  id: string
  role: string
  content: string | null
  created_at: string
}

interface Conversation {
  id: string
  title: string | null
  created_at: string
  messages: Message[]
}

export default function ConversationPage({ id }: { id: string }) {
  const { user, loading } = useAuth()
  const router = useRouter()
  const [conversation, setConversation] = useState<Conversation | null>(null)
  const [fetching, setFetching] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (loading) return
    if (!user) {
      router.replace("/signup")
      return
    }
    const fetchConversation = async () => {
      try {
        const token = await getAccessToken()
        const res = await fetch(`${API_BASE}/api/v1/conversations/${id}`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (res.status === 404) {
          router.replace("/buildhistory")
          return
        }
        if (!res.ok) throw new Error(`${res.status}`)
        setConversation(await res.json())
      } catch {
        setError("Failed to load this conversation.")
      } finally {
        setFetching(false)
      }
    }
    fetchConversation()
  }, [id, user, loading, router])

  if (loading || fetching) return null

  if (error) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <p className="text-sm text-destructive">{error}</p>
      </div>
    )
  }

  if (!conversation) return null

  const chatMessages = conversation.messages.filter(
    (m) => m.role === "user" || m.role === "assistant"
  )

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-3 px-6 py-4 border-b shrink-0">
        <button
          onClick={() => router.push("/buildhistory")}
          className="rounded-md p-1 hover:bg-accent text-muted-foreground"
          aria-label="Back to builds"
        >
          <ArrowLeft className="h-4 w-4" />
        </button>
        <div className="min-w-0">
          <h1 className="font-semibold truncate">
            {conversation.title ?? "Untitled Build"}
          </h1>
          <p className="text-xs text-muted-foreground">
            {new Date(conversation.created_at).toLocaleDateString(undefined, {
              year: "numeric",
              month: "long",
              day: "numeric",
            })}
          </p>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
        {chatMessages.map((msg) => {
          const isUser = msg.role === "user"
          return (
            <div
              key={msg.id}
              className={`flex gap-3 ${isUser ? "flex-row-reverse" : "flex-row"}`}
            >
              <div className="shrink-0 rounded-full bg-muted p-1.5 h-7 w-7 flex items-center justify-center">
                {isUser
                  ? <User className="h-3.5 w-3.5 text-muted-foreground" />
                  : <Image src="/assets/images/palladium-logo.svg" alt="Palladium" width={14} height={14} />
                }
              </div>
              <div
                className={`max-w-[75%] rounded-2xl px-4 py-2.5 text-sm whitespace-pre-wrap ${
                  isUser
                    ? "bg-primary text-primary-foreground rounded-tr-sm"
                    : "bg-muted rounded-tl-sm"
                }`}
              >
                {msg.content ?? ""}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
