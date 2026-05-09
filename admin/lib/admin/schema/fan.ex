defmodule Admin.Schema.Fan do
  use Ecto.Schema
  import Ecto.Changeset

  @primary_key {:id, Ecto.UUID, autogenerate: true}

  schema "fans" do
    field :name, :string, virtual: true
    field :manufacturer, :string, virtual: true
    field :model_number, :string, virtual: true
    field :year_released, :integer, virtual: true
    field :is_active, :boolean, virtual: true, default: true

    field :size_mm, :integer
    field :max_rpm, :integer
    field :airflow_cfm, :float
    field :noise_dba, :float
    field :is_pwm, :boolean
    field :has_rgb, :boolean
    field :bearing_type, :string
    field :is_static_pressure, :boolean
    field :pack_count, :integer
  end

  def changeset(fan, attrs, _metadata \\ %{}) do
    fan
    |> cast(attrs, [
      :name, :manufacturer, :model_number, :year_released, :is_active,
      :size_mm, :max_rpm, :airflow_cfm, :noise_dba, :is_pwm,
      :has_rgb, :bearing_type, :is_static_pressure, :pack_count
    ])
    |> validate_required([:name, :size_mm])
    |> prepare_changes(&upsert_pc_part(&1, "fan"))
  end

  defp upsert_pc_part(changeset, part_type) do
    repo = changeset.repo
    id = get_field(changeset, :id)

    %Admin.Schema.PCPart{id: id}
    |> Ecto.Changeset.cast(
      %{
        name: get_field(changeset, :name),
        manufacturer: get_field(changeset, :manufacturer),
        model_number: get_field(changeset, :model_number),
        year_released: get_field(changeset, :year_released),
        is_active: get_field(changeset, :is_active) || true,
        part_type: part_type
      },
      [:name, :manufacturer, :model_number, :year_released, :is_active, :part_type]
    )
    |> repo.insert!(
      on_conflict: {:replace_all_except, [:id, :part_type, :created_at]},
      conflict_target: :id
    )

    changeset
  end
end
