import ConversationPage from "@/components/pages/ConversationPage"

export default function Page({ params }: { params: { id: string } }) {
  return <ConversationPage id={params.id} />
}
