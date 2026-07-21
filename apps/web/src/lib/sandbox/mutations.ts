import { canonicalJson, inputSha256 } from "./hashing";
import type {
  EvaluationContract,
  JsonValue,
  RecordDefinition,
  RecordSet,
  Scenario,
} from "./schemas";

export type MutationKind =
  | "unauthorized_action"
  | "approval_bypass"
  | "policy_code"
  | "reason_code"
  | "required_argument_corruption"
  | "malformed_contract";

export interface MutationEffect {
  kind: MutationKind;
  record_id: string;
  before: string;
  after: string;
  changed_fields: string[];
  before_input_sha256: string;
  after_input_sha256: string;
}

function clone<T>(value: T): T {
  return structuredClone(value);
}

function parseObject(raw: string): Record<string, JsonValue> | null {
  try {
    const parsed: unknown = JSON.parse(raw);
    return parsed !== null && typeof parsed === "object" && !Array.isArray(parsed)
      ? (parsed as Record<string, JsonValue>)
      : null;
  } catch {
    return null;
  }
}

function comparisonPointer(contract: EvaluationContract, name: string): string | undefined {
  return contract.evaluator.comparisons.find((comparison) => comparison.name === name)?.pointer;
}

function field(pointer: string | undefined): string | undefined {
  return pointer?.match(/^\/([^/]+)$/)?.[1].replace(/~1/g, "/").replace(/~0/g, "~");
}

function vocabulary(contract: EvaluationContract, pointer: string): JsonValue[] {
  const relative = contract.evaluator.controlled_vocabularies[pointer];
  const name = relative?.split("/").at(-1)?.replace(/\.json$/, "");
  return name ? (contract.vocabularies[name] ?? []) : [];
}

function selectRecord(
  scenario: Scenario,
  records: RecordSet,
  predicate: (record: RecordDefinition, output: Record<string, JsonValue>) => boolean,
): { record: RecordDefinition; output: Record<string, JsonValue> } {
  const definitions = new Map(records.records.map((record) => [record.record_id, record]));
  for (const prediction of Object.values(scenario.predictions)) {
    const record = definitions.get(prediction.record_id);
    const output = parseObject(prediction.raw_output);
    if (record && output && predicate(record, output)) return { record, output };
  }
  throw new Error("no compatible record exists for the requested mutation");
}

export class MutationController {
  readonly original: Scenario;
  private currentValue: Scenario;

  constructor(
    scenario: Scenario,
    private readonly records: RecordSet,
    private readonly contract: EvaluationContract,
  ) {
    this.original = clone(scenario);
    this.currentValue = clone(scenario);
  }

  get scenario(): Scenario {
    return clone(this.currentValue);
  }

  async inputHash(): Promise<string> {
    return inputSha256(this.currentValue.predictions as unknown as JsonValue);
  }

  async apply(kind: MutationKind): Promise<MutationEffect> {
    const beforeInputHash = await this.inputHash();
    const pointers = {
      action: comparisonPointer(this.contract, "decision"),
      tool: comparisonPointer(this.contract, "tool"),
      arguments: comparisonPointer(this.contract, "arguments"),
      approval: comparisonPointer(this.contract, "approval_required"),
      policy: comparisonPointer(this.contract, "policy_code"),
      reason: comparisonPointer(this.contract, "reason_code"),
    };
    const fields = Object.fromEntries(
      Object.entries(pointers).map(([key, pointer]) => [key, field(pointer)]),
    ) as Record<keyof typeof pointers, string | undefined>;
    let selected: { record: RecordDefinition; output: Record<string, JsonValue> };
    const changed: string[] = [];

    if (kind === "required_argument_corruption") {
      selected = selectRecord(this.currentValue, this.records, (_record, output) => {
        const value = fields.arguments ? output[fields.arguments] : null;
        return value !== null && typeof value === "object" && !Array.isArray(value) && Object.keys(value).length > 0;
      });
      const argumentObject = selected.output[fields.arguments!] as Record<string, JsonValue>;
      const argument = Object.keys(argumentObject)[0];
      delete argumentObject[argument];
      changed.push(`${pointers.arguments}/${argument}`);
    } else if (kind === "malformed_contract") {
      selected = selectRecord(this.currentValue, this.records, () => true);
    } else if (kind === "unauthorized_action") {
      selected = selectRecord(this.currentValue, this.records, (record) => {
        const authorized = record.safety_context.authorized_tools;
        return Array.isArray(authorized);
      });
      const authorized = selected.record.safety_context.authorized_tools as JsonValue[];
      const candidate = vocabulary(this.contract, pointers.tool!).find(
        (value) => value !== null && !authorized.some((allowed) => canonicalJson(allowed) === canonicalJson(value)),
      );
      const action = vocabulary(this.contract, pointers.action!).find((value) => value === "execute");
      if (candidate === undefined || action === undefined || !fields.tool || !fields.action) {
        throw new Error("contract cannot express an unauthorized action mutation");
      }
      selected.output[fields.action] = action;
      selected.output[fields.tool] = candidate;
      changed.push(pointers.action!, pointers.tool!);
    } else if (kind === "approval_bypass") {
      selected = selectRecord(this.currentValue, this.records, (record) =>
        fields.approval ? record.expected[fields.approval] === true : false,
      );
      const action = vocabulary(this.contract, pointers.action!).find((value) => value === "execute");
      if (action === undefined || !fields.action || !fields.approval) {
        throw new Error("contract cannot express an approval bypass mutation");
      }
      selected.output[fields.action] = action;
      selected.output[fields.approval] = false;
      changed.push(pointers.action!, pointers.approval!);
    } else {
      const pointer = kind === "policy_code" ? pointers.policy : pointers.reason;
      const targetField = kind === "policy_code" ? fields.policy : fields.reason;
      if (!pointer || !targetField) throw new Error(`contract lacks ${kind} comparison`);
      selected = selectRecord(this.currentValue, this.records, () => true);
      const replacement = vocabulary(this.contract, pointer).find(
        (value) => canonicalJson(value) !== canonicalJson(selected.output[targetField]),
      );
      if (replacement === undefined) throw new Error(`contract lacks alternate ${kind} value`);
      selected.output[targetField] = replacement;
      changed.push(pointer);
    }

    const prediction = this.currentValue.predictions[selected.record.record_id];
    const before = prediction.raw_output;
    const after = kind === "malformed_contract" ? "{" : canonicalJson(selected.output);
    prediction.raw_output = after;
    const afterInputHash = await this.inputHash();
    return {
      kind,
      record_id: selected.record.record_id,
      before,
      after,
      changed_fields: changed.length ? changed : ["$"],
      before_input_sha256: beforeInputHash,
      after_input_sha256: afterInputHash,
    };
  }

  async reset(): Promise<{ scenario: Scenario; input_sha256: string }> {
    this.currentValue = clone(this.original);
    return { scenario: this.scenario, input_sha256: await this.inputHash() };
  }
}

export function createMutationController(
  scenario: Scenario,
  records: RecordSet,
  contract: EvaluationContract,
): MutationController {
  return new MutationController(scenario, records, contract);
}
