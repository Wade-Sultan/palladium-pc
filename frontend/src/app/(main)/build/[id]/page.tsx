import ConversationPage from "@/components/pages/ConversationPage"

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  return <ConversationPage id={id} />
}
