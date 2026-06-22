"use client";

import { useState, useEffect } from "react";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { databasesApi, type DatabaseOptions } from "@/lib/databases";
import { ApiError } from "@/lib/api-client";

interface CreateDatabaseDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: () => void;
}

export function CreateDatabaseDialog({ open, onOpenChange, onCreated }: CreateDatabaseDialogProps) {
  const [options, setOptions] = useState<DatabaseOptions | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [engine, setEngine] = useState("mysql");
  const [maxConnections, setMaxConnections] = useState("50");

  useEffect(() => {
    if (open) {
      databasesApi.options()
        .then(setOptions)
        .catch(() => setOptions(null));
    }
  }, [open]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await databasesApi.create({
        name,
        engine,
        max_connections: parseInt(maxConnections, 10) || 50,
      });
      onOpenChange(false);
      setName("");
      setEngine("mysql");
      setMaxConnections("50");
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create database");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Create Database</DialogTitle>
          <DialogDescription>
            Provision a new database on MySQL, MariaDB, PostgreSQL or SQL Server.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="db-name">Database Name</Label>
            <Input
              id="db-name"
              placeholder="myapp_db"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              pattern="[a-z][a-z0-9_]{1,62}"
            />
          </div>
          <div className="space-y-2">
            <Label>Engine</Label>
            <Select value={engine} onValueChange={setEngine}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {(options?.engines || [
                  { engine: "mysql", label: "MySQL" },
                  { engine: "mariadb", label: "MariaDB" },
                  { engine: "postgresql", label: "PostgreSQL" },
                  { engine: "mssql", label: "Microsoft SQL Server" },
                ]).map((opt) => (
                  <SelectItem key={opt.engine} value={opt.engine}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="max-conn">Max Connections</Label>
            <Input
              id="max-conn"
              type="number"
              min={1}
              max={1000}
              value={maxConnections}
              onChange={(e) => setMaxConnections(e.target.value)}
            />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={loading}>
              {loading && <Loader2 className="h-4 w-4 animate-spin" />}
              Create
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
