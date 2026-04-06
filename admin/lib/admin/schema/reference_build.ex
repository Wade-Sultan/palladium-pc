defmodule Admin.Schema.ReferenceBuild do
  use Ecto.Schema
  import Ecto.Changeset

  @primary_key {:id, Ecto.UUID, autogenerate: false}

  schema "reference_builds" do
    field :build_key, :string
    field :label, :string
    field :description, :string
    field :total_approx, :integer
    field :is_active, :boolean, default: true

    timestamps(type: :utc_datetime, inserted_at: :created_at, updated_at: :updated_at)
  end

  def changeset(build, attrs, _metadata \\ %{}) do
    build
    |> cast(attrs, [:build_key, :label, :description, :total_approx, :is_active])
    |> validate_required([:build_key, :label, :description])
    |> unique_constraint(:build_key)
  end
end
