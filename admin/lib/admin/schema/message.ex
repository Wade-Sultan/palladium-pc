defmodule Admin.Schema.Message do
  use Ecto.Schema

  @primary_key {:id, Ecto.UUID, autogenerate: false}
  @foreign_key_type Ecto.UUID

  schema "messages" do
    field :conversation_id, Ecto.UUID
    field :role, :string
    field :content, :string
    field :metadata, :map

    field :created_at, :utc_datetime
  end
end
