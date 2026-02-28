package com.ba.bluearchivemusicapi.entities;

import jakarta.persistence.*;
import lombok.*;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;

@Setter
@Getter
@AllArgsConstructor
@NoArgsConstructor
@Entity
@Builder
@Table(name = "album")
public class Album {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "title")
    private String title;

    @Column(name = "cover_image_path")
    private String coverImagePath;

    @Column(name = "release_date")
    private String releaseDate;

    @Column(name = "description")
    private String description;

    @Column(name = "created_date")
    private LocalDate createdDate;

    @Column(name = "updated_date")
    private LocalDate updatedDate;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "category_id")
    private Category category;

    @OneToMany(mappedBy = "album",
            cascade = CascadeType.ALL,
            orphanRemoval = true,
            fetch = FetchType.LAZY)
    private List<Song> songList = new ArrayList<>();

    // ──── Helper methods ────
    public void addSong(Song song) {
        songList.add(song);
        song.setAlbum(this);
    }

    public void removeSong(Song song) {
        songList.remove(song);
        song.setAlbum(null);
    }
}
