defmodule Admin.Schema.PCPart do
  use Ecto.Schema
  import Ecto.Changeset

  @primary_key {:id, Ecto.UUID, autogenerate: false}

  schema "pc_parts" do
    field :name, :string
    field :manufacturer, :string
    field :model_number, :string
    field :year_released, :integer
    field :part_type, :string
    field :is_active, :boolean, default: true

    timestamps(type: :utc_datetime, inserted_at: :created_at, updated_at: :updated_at)
  end

  def changeset(pc_part, attrs, _metadata \\ %{}) do
    pc_part
    |> cast(attrs, [:name, :manufacturer, :model_number, :year_released, :is_active])
    |> validate_required([:name])
  end
end
