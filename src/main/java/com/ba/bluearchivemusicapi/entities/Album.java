package com.ba.bluearchivemusicapi.entities;

import jakarta.persistence.*;
import lombok.*;
import org.springframework.data.annotation.CreatedDate;
import org.springframework.data.annotation.LastModifiedDate;
import org.springframework.data.jpa.domain.support.AuditingEntityListener;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;

@Setter
@Getter
@AllArgsConstructor
@NoArgsConstructor
@Entity
@Builder
@EntityListeners(AuditingEntityListener.class)
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
    private LocalDate releaseDate;

    @Column(name = "description")
    private String description;

    @CreatedDate
    @Column(name = "created_date")
    private LocalDate createdDate;

    @LastModifiedDate
    @Column(name = "updated_date")
    private LocalDate updatedDate;

    @ManyToOne
    @JoinColumn(name = "category_id")
    private Category category;

    @OneToMany(mappedBy = "album")
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
